"""
caspi: the course Raspberry Pi from Python, no ssh needed.

    import caspi
    caspi.connect()            run this first, it waits for the Pi to boot

The Pi runs Ollama on port 11434 and a small course server on port 8000.
Everything here is a plain HTTP request, so read it, copy from it, change it.

Models. Every call names its model, so you always know which one answered.
    caspi.models()                                  what is on the Pi
    caspi.ask("lfm2.5", "Why is the sky blue?")
    caspi.ask("lfm2.5", "...", system="Answer in one line.", temperature=0.2)
    caspi.chat("lfm2.5", [{"role": "user", "content": "Hi, I am Ana."}])
    caspi.repl("lfm2.5")                            a chat right in the cell
    caspi.embed("all-minilm", "some text")

    Model options are keywords: temperature, top_k, top_p, min_p, seed,
    num_predict, num_ctx, stop, repeat_penalty, ... and so are request fields:
    format, think, tools, raw, images, logprobs, keep_alive, ...
    stream=False waits for the whole answer, show=False prints nothing
    (the timing line included), stats=False only skips the timing line.

    reply = caspi.ask(...)
    reply.text  reply.thinking  reply.tool_calls  reply.stats  reply.raw
    history.append(reply.message)                   keeps a chat going

    caspi.show("lfm2.5")                            architecture, size, defaults
    caspi.ps()  caspi.load(m)  caspi.stop(m)        what is in memory
    caspi.stop()                                    frees the memory: drops every model
    caspi.ollama("/api/version")                    any other endpoint, as JSON

The Pi
    caspi.health()                                  mode, image, temperature, disk
    caspi.scripts()                                 what it can run
    caspi.run("hello")                              output streams in
    caspi.update(url)                               install new course scripts

The quiz of 05.19
    caspi.quiz(answer)                              the practice test, scored and timed

Settings, change them any time
    caspi.KEEP_ALIVE = "30m"                        how long a model stays loaded
    caspi.TIMEOUT = 900                             seconds to wait for the Pi
"""

import json
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from difflib import get_close_matches

import requests

__version__ = "2.6"

# Fixed by the Pi image (cas-setup.sh), so not a setting.
HOST = "172.31.250.1"
OLLAMA = f"http://{HOST}:11434"
SERVER = f"http://{HOST}:8000"

KEEP_ALIVE = "30m"  # loading a model off the SD card takes minutes, so keep it around
TIMEOUT = 900       # a cold model load alone can take four minutes
CONNECT = 10        # a lost packet is resent after 1 s (Linux) or 3 s (Windows)

# The model options Ollama knows (Options in its api/types.go, the same in 0.34 and 0.40).
# It silently ignores any other name, so temprature=0.1 would change nothing without
# a word. caspi refuses it instead.
OPTIONS = {"temperature", "top_k", "top_p", "min_p", "typical_p", "seed", "num_predict",
           "num_ctx", "stop", "repeat_penalty", "repeat_last_n", "presence_penalty",
           "frequency_penalty", "num_keep", "num_batch", "num_thread", "num_gpu", "main_gpu",
           "use_mmap", "draft_num_predict"}

# Request fields that sit next to "options" instead of inside it.
FIELDS = {"format", "think", "tools", "images", "raw", "template", "suffix", "context",
          "keep_alive", "logprobs", "top_logprobs", "truncate", "dimensions"}


class PiError(RuntimeError):
    """The Pi could not do what was asked. The message says what to try."""


def _call(method, base, path, **kwargs):
    try:
        response = requests.request(method, base + path, timeout=(CONNECT, TIMEOUT), **kwargs)
    except requests.RequestException as error:
        raise PiError(f"no answer from {base + path} ({type(error).__name__}).\n"
                      f"Is the Pi on and plugged in? caspi.connect() waits for it.") from None
    if not response.ok:
        raise PiError(f"{path} failed: {_error_text(response.text)}")
    return response


def _error_text(text):
    """The message of an error response. Ollama 0.40 can wrap it in a second layer of JSON."""
    message = text.strip()
    for _ in range(2):
        try:
            inner = json.loads(message)["error"]
        except (ValueError, KeyError, TypeError):
            break
        message = inner["message"] if isinstance(inner, dict) else str(inner)
    return message


def _lines(response):
    """Ollama answers with one JSON object per line. With "stream": False that
    is a single line, so the same loop reads both."""
    try:
        for line in response.iter_lines():
            if line:
                message = json.loads(line)
                if "error" in message:
                    raise PiError(f"Ollama: {message['error']}")
                yield message
    except requests.RequestException:
        raise PiError("the connection to the Pi dropped in the middle of the answer") from None


# ---------------------------------------------------------------- models

@dataclass
class Reply:
    """What ask() and chat() give back. str(reply) is the answer."""
    model: str
    text: str = ""
    thinking: str = ""
    tool_calls: list = field(default_factory=list)
    logprobs: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)  # Ollama's last object: timings, done_reason, ...
    shown: bool = True

    def __str__(self):
        return self.text

    @property
    def message(self):
        """The reply as a chat message, ready to append to a history."""
        message = {"role": "assistant", "content": self.text}
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls
        return message

    @property
    def stats(self):
        """Ollama's own counts and timings for this reply, in seconds."""
        def seconds(key):
            return self.raw.get(key, 0) / 1e9

        def rate(tokens, duration):
            return tokens / duration if duration else 0

        prompt, reply = self.raw.get("prompt_eval_count", 0), self.raw.get("eval_count", 0)
        # Ollama keeps the start of the last prompt in memory and only reads the
        # rest, so the prompt speed counts the tokens it actually read.
        cached = self.raw.get("prompt_eval_cached_count", 0)
        return {
            "prompt_tokens": prompt,
            "prompt_cached_tokens": cached,
            "prompt_seconds": seconds("prompt_eval_duration"),
            "prompt_tokens_per_s": rate(prompt - cached, seconds("prompt_eval_duration")),
            "reply_tokens": reply,
            "reply_seconds": seconds("eval_duration"),
            "reply_tokens_per_s": rate(reply, seconds("eval_duration")),
            "load_seconds": seconds("load_duration"),
            "total_seconds": seconds("total_duration"),
        }

    def _ipython_display_(self):
        # A notebook prints the value of a cell's last line. The answer already
        # streamed into the cell, so don't print it a second time.
        if not self.shown:
            print(self.text)


def _body(model, params):
    """Sort keyword arguments into request fields and model options."""
    body = {"model": model, "keep_alive": KEEP_ALIVE}
    options = dict(params.pop("options", {}))  # an options={...} dict works too
    for key, value in params.items():
        if key in FIELDS:
            body[key] = value
        else:
            options[key] = value
    for key in options:
        if key not in OPTIONS:
            guess = get_close_matches(key, OPTIONS | FIELDS, n=1)
            raise TypeError(f"Ollama has no option {key!r}"
                            + (f", did you mean {guess[0]!r}?" if guess else ""))
    if options:
        body["options"] = options
    return body


def ask(model, prompt, system=None, stream=True, show=True, stats=None, **params):
    """One prompt, one answer (/api/generate). Prints as it streams, returns a Reply.

        caspi.ask("lfm2.5", "Why is the sky blue?")
        caspi.ask("lfm2.5", "Name a colour.", temperature=1.5, seed=7, num_predict=20)
        caspi.ask("granite4.2:3b", "Three facts about Zurich, as JSON.", format="json")
        reply = caspi.ask("lfm2.5", "...", show=False)
    """
    body = _body(model, params)
    body.update(prompt=prompt, stream=stream)
    if system:
        body["system"] = system
    return _generate("/api/generate", body, show, stats)


def chat(model, messages, system=None, stream=True, show=True, stats=None, **params):
    """A conversation (/api/chat). messages is a string or a list of
    {"role": ..., "content": ...} dicts. Returns a Reply.

        history = [{"role": "user", "content": "My name is Ana."}]
        reply = caspi.chat("lfm2.5", history)
        history += [reply.message, {"role": "user", "content": "What is my name?"}]
        caspi.chat("lfm2.5", history)

    With tools=[...] the model may ask for a tool instead: see reply.tool_calls.
    """
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    if system:
        messages = [{"role": "system", "content": system}] + messages
    body = _body(model, params)
    body.update(messages=messages, stream=stream)
    return _generate("/api/chat", body, show, stats)


def _generate(path, body, show, stats):
    model = body["model"]
    if show and not _in_memory(model):
        print(f"(loading {model} into memory, this can take a few minutes)", flush=True)

    reply = Reply(model, shown=show)
    with _call("POST", OLLAMA, path, json=body, stream=True) as response:
        for message in _lines(response):
            part = message.get("message", message)  # /api/chat nests one level deeper
            thought = part.get("thinking") or ""
            words = part.get("content") or part.get("response") or ""
            if thought:
                if show and not reply.thinking:
                    print("Thinking...")
                reply.thinking += thought
            if words and show and reply.thinking and not reply.text:
                print("\n...done thinking.\n")
            reply.text += words
            if show:
                print(thought + words, end="", flush=True)
            for call in part.get("tool_calls") or []:
                reply.tool_calls.append(call)
                if show:
                    print(f"[tool call] {call['function']['name']}({call['function']['arguments']})")
            reply.logprobs += message.get("logprobs") or []
            reply.raw = message

    if show and reply.text:
        print()
    # Some models write their reasoning into the answer instead of Ollama's
    # thinking field: lfm2.5 as <think>...</think>, granite4.2 on /api/generate
    # with only the closing tag, because its prompt already opened it. Split it
    # off. An answer that really mentions </think> gets cut there too, rare enough.
    head, closed, tail = reply.text.partition("</think>")
    if closed or head.lstrip().startswith("<think>"):
        reply.thinking += head.replace("<think>", "", 1).strip()
        reply.text = tail
    reply.text = reply.text.strip()
    if stats is None:
        stats = show   # no answer on screen, no timing line either
    if stats:
        _print_stats(reply)
    return reply


def _in_memory(model):
    names = {entry["name"] for entry in ps()}
    return model in names or f"{model}:latest" in names


def _print_stats(reply):
    s = reply.stats
    cached = f" ({s['prompt_cached_tokens']} cached)" if s["prompt_cached_tokens"] else ""
    print(f"\n[{reply.model}] "
          f"prompt {s['prompt_tokens']} tok{cached} in {s['prompt_seconds']:.1f} s "
          f"({s['prompt_tokens_per_s']:.1f} tok/s) | "
          f"reply {s['reply_tokens']} tok in {s['reply_seconds']:.1f} s "
          f"({s['reply_tokens_per_s']:.1f} tok/s) | "
          f"load {s['load_seconds']:.1f} s | total {s['total_seconds']:.1f} s")


def repl(model, system=None, **params):
    """A chat in the cell, like `ollama run lfm2.5` over ssh. /reset forgets
    everything said so far, /bye ends it.

    In a notebook you type into a box under the cell, and the cell is free again
    right away. Elsewhere it reads from a >>> prompt and returns the conversation
    when you type /bye."""
    history = []

    def say(said):
        """One turn of the chat. False means the chat is over."""
        said = said.strip()
        if said in ("/bye", "/exit"):
            return False
        if said == "/reset":
            history.clear()
            print("(forgotten)")
        elif said:
            history.append({"role": "user", "content": said})
            try:
                history.append(chat(model, history, system=system, stats=False, **params).message)
            except (KeyboardInterrupt, PiError) as error:
                print(f"\n({str(error) or 'stopped'})")
                history.pop()
        return True

    print(f"Chatting with {model}. /reset forgets, /bye ends.")
    if _in_notebook():
        _chat_box(say)
        return None
    while True:
        try:
            if not say(input("\n>>> ")):
                return history
        except (EOFError, KeyboardInterrupt):
            return history


def _in_notebook():
    """True in a Jupyter kernel (VS Code, JupyterLab), where ipywidgets can draw."""
    try:
        import ipywidgets  # noqa: F401
        from IPython import get_ipython
    except ImportError:
        return False
    return getattr(get_ipython(), "kernel", None) is not None


def _chat_box(say):
    """repl() in a notebook: a text box under the cell. input() would open
    VS Code's prompt bar at the top of the window instead.

    The conversation is the text of an HTML widget, set from here. An Output
    widget would be simpler, but VS Code showed everything in it three times."""
    import html
    from contextlib import redirect_stdout

    import ipywidgets
    from IPython.display import display

    log = ipywidgets.HTML()
    box = ipywidgets.Text(placeholder="Type here and press Enter", continuous_update=False,
                          layout={"width": "100%"})

    class Log:
        """Takes what print() writes during the chat and shows it in the widget."""
        text = ""

        def write(self, part):
            self.text += part
            log.value = f"<pre style='white-space: pre-wrap'>{html.escape(self.text)}</pre>"

        def flush(self):
            pass

    chat_log = Log()

    def typed(change):
        said = change["new"]
        if not said:
            return
        box.value = ""  # comes back in here as "", which the line above ignores
        with redirect_stdout(chat_log):
            print(f"\n>>> {said}")
            if not say(said):
                box.disabled = True
                print("(chat ended)")

    box.observe(typed, names="value")
    display(log, box)


def embed(model, text, **params):
    """Text to vector (/api/embed). A list of texts gives a list of vectors.

        vector = caspi.embed("all-minilm", "an unknown node transmits politely")
        vectors = caspi.embed("all-minilm", ["card one", "card two"])
    """
    body = _body(model, params)
    body["input"] = text
    vectors = ollama("/api/embed", body)["embeddings"]
    return vectors[0] if isinstance(text, str) else vectors


def models(info=False):
    """Names of the models on the Pi. info=True adds size and quantization."""
    entries = sorted(ollama("/api/tags")["models"], key=lambda entry: entry["name"])
    if not info:
        return [entry["name"] for entry in entries]
    return [{"name": entry["name"],
             "size_gb": round(entry["size"] / 1e9, 2),
             "parameters": entry["details"].get("parameter_size"),
             "quantization": entry["details"].get("quantization_level")} for entry in entries]


def show(model):
    """What a model is: architecture, size, context, capabilities, defaults.
    The full JSON, with template, license and tensors:
        caspi.ollama("/api/show", {"model": "lfm2.5"})
    """
    info = ollama("/api/show", {"model": model})
    details, meta = info["details"], info["model_info"]
    arch = meta["general.architecture"]
    defaults = [" ".join(line.split()) for line in info.get("parameters", "").splitlines()]
    print(model)
    print(f"  architecture   {arch}, {details['parameter_size']} parameters, "
          f"{details['quantization_level']}")
    print(f"  context        up to {meta.get(f'{arch}.context_length', '?')} tokens")
    print(f"  embedding      {meta.get(f'{arch}.embedding_length', '?')} dimensions")
    print(f"  capabilities   {', '.join(info.get('capabilities', []))}")
    print(f"  defaults       {', '.join(defaults) or 'none'}")


def ps():
    """The models in memory right now, and when Ollama will drop them."""
    return ollama("/api/ps")["models"]


def load(model):
    """Load a model into memory now, so the first real question is not the slow one."""
    started = time.monotonic()
    print(f"loading {model} ...", flush=True)
    ollama("/api/generate", {"model": model, "keep_alive": KEEP_ALIVE, "stream": False})
    print(f"{model} is loaded ({time.monotonic() - started:.0f} s) "
          f"and stays for {KEEP_ALIVE} after each use")


def stop(model=None):
    """Drop a model from memory. Without a model, drop every model: run caspi.stop()
    before you load a large one, because two large models can freeze the Pi."""
    if model:
        ollama("/api/generate", {"model": model, "keep_alive": 0, "stream": False})
        return
    names = [entry["name"] for entry in ps()]
    if not names:
        print("no model was loaded")
        return
    print(f"stopping {', '.join(names)} ...", flush=True)
    for name in names:
        stop(name)
    # Ollama frees the memory in the background, which can take a minute, and
    # not while a model is still answering a request.
    left = names
    deadline = time.monotonic() + 90
    while left and time.monotonic() < deadline:
        time.sleep(1)
        left = [entry["name"] for entry in ps()]
    if left:
        print(f"{', '.join(left)} is still in memory, probably still answering a request")
    else:
        print("the memory is free")


def ollama(path, body=None):
    """Any Ollama endpoint, for whatever is not wrapped above. Returns the JSON.

        caspi.ollama("/api/version")
        caspi.ollama("/api/show", {"model": "lfm2.5"})["template"]
        caspi.ollama("/api/generate", {"model": "lfm2.5", "prompt": "Hi", "stream": False})

    /api/generate and /api/chat stream unless the body says "stream": False.
    """
    if body is None:
        return _call("GET", OLLAMA, path).json()
    return _call("POST", OLLAMA, path, json=body).json()


# ---------------------------------------------------------------- the Pi

def connect(timeout=60):
    """Wait until the Pi and its Ollama answer, then say what is there.
    Fine to run right after switching the Pi on: it keeps trying for `timeout` seconds."""
    print(f"looking for the Pi at {HOST} ...", flush=True)
    deadline = time.monotonic() + timeout
    report = names = None
    while names is None:
        try:
            report = health()
            names = models()
        except PiError:
            if time.monotonic() > deadline:
                raise PiError(_why_not(report, timeout)) from None
            time.sleep(2)

    image = report["image"].get("cas_image_version", "?")
    print(f"Connected to {report['hostname']} at {HOST}: {report['mode']} mode, image {image}, "
          f"up {report['uptime_seconds'] // 60} min, {report['cpu_temp_c']} C, "
          f"{report['disk_free_gb']} GB free")
    print(f"Ollama {report['ollama']['version']}: {', '.join(names) or 'no models'}")
    print(f"Scripts: {', '.join(report['scripts']) or 'none'}")
    loaded = [entry["name"] for entry in ps()]
    if loaded:
        print(f"In memory: {', '.join(loaded)}. Before you load a large model, free it with caspi.stop().")


def _why_not(report, timeout):
    if report is None:
        return (f"no answer from the Pi at {HOST} within {timeout} s.\n"
                f"Is it switched on (it needs about a minute to boot) "
                f"and the cable in at both ends?")
    if not report["ollama"]["reachable"]:
        return "the Pi is up, but Ollama is not running on it yet. Wait a minute and run this again."
    return (f"Ollama runs on the Pi, but this laptop cannot reach {OLLAMA}.\n"
            f"A VPN or firewall on the laptop is the usual cause.")


def health():
    """The Pi's own report: hostname, mode, image, uptime, temperature, disk, scripts."""
    return _call("GET", SERVER, "/health").json()


def scripts():
    """The scripts this Pi can run."""
    return health()["scripts"]


@dataclass
class ScriptRun:
    """What run() gives back. str(result) is the output."""
    script: str
    output: str
    exit_code: int
    data: object = None  # from the script's final `#json {...}` line, if it printed one
    shown: bool = True

    @property
    def ok(self):
        return self.exit_code == 0

    def __str__(self):
        return self.output

    def _ipython_display_(self):
        # Same as Reply: the output already streamed into the cell.
        if not self.shown:
            print(self.output)


def run(script, *args, timeout=None, show=True):
    """Run one of the Pi's scripts and stream its output. caspi.scripts() lists them.

        caspi.run("hello")
        caspi.run("hello", "an argument")
        caspi.run("strategy-react", "Node B is jamming again", timeout=600)
        result = caspi.run("hello", show=False)

    The Pi stops a script after 10 minutes unless you give a timeout. A script can
    hand back data as well as text by printing one last line `#json {...}`.
    That line is not printed; it ends up in result.data.
    """
    params = [("args", str(arg)) for arg in args]
    if timeout:
        params.append(("timeout", timeout))

    lines, data, exit_code = [], None, 0
    with _call("GET", SERVER, f"/script/{script}", params=params, stream=True) as response:
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith("#json"):
                data = json.loads(line[len("#json"):])
                continue
            if line.startswith("[cas-server]"):  # the server's note when a script fails or times out
                code = re.search(r"exited with code (-?\d+)", line)
                exit_code = int(code[1]) if code else -1
            lines.append(line)
            if show:
                print(line, flush=True)
    return ScriptRun(script, "\n".join(lines), exit_code, data, show)


def update(source=None, timeout=600):
    """Install new course scripts from a tarball URL. Without one, the Pi uses
    the URL in its /etc/cas-update-url. This laptop works as the source:

        python3 -m http.server 8080          in the folder with the tarball
        caspi.update("http://<laptop-ip>:8080/cas.tar.gz")
    """
    args = [source] if source else []
    return run("update", *args, timeout=timeout)


# ---------------------------------------------------------------- the 05.19 quiz

# The practice test: (question, accepted answers). None means the question is about
# something that does not exist, so "does not exist" is the right answer.
QUIZ = [
    ("What is the capital of Switzerland?", ["Bern", "Berne"]),
    ("Who is the mayor of the Swiss village of Grünwilerberg?", None),
    ("Which chemical element has the symbol Fe?", ["iron"]),
    ("In which year did Switzerland join the United Nations?", ["2002"]),
    ("Which river flows through Basel?", ["Rhine", "Rhein"]),
    ("What is the atomic number of the element zurichium?", None),
    ("How many bits are in a byte?", ["8", "eight"]),
    ("Who wrote the 1804 play Wilhelm Tell?", ["Schiller"]),
    ("In which frequency band is Wi-Fi channel 6?", ["2.4 GHz", "2.4", "2.4GHz"]),
    ("What is the capital of the Swiss canton of Gotthard?", None),
    ("Who is known as the father of information theory?", ["Shannon"]),
    ("Which planet is the largest in the solar system?", ["Jupiter"]),
    ("Near which city is CERN located?", ["Geneva", "Genève", "Genf", "Meyrin"]),
    ("In which year did the Gotthard Hyperloop open?", None),
    ("What does the abbreviation LTE stand for?", ["Long Term Evolution"]),
    ("How many cantons does Switzerland have?", ["26", "twenty-six"]),
    ("Which gas makes up most of the Earth's atmosphere?", ["nitrogen", "N2"]),
    ("Who was the first president of the Republic of Valtoria?", None),
    ("In which city was the mathematician Leonhard Euler born?", ["Basel"]),
    ("What is the smallest prime number?", ["2", "two"]),
    ("What is the highest mountain in the Alps?", ["Mont Blanc", "Monte Bianco"]),
    ("Who wrote the 1923 novel The Glass Antenna?", None),
    ("In which Swiss city did Albert Einstein work at the patent office?", ["Bern", "Berne"]),
    ("What is the chemical symbol for gold?", ["Au"]),
    ("What is the largest lake entirely within Switzerland?", ["Neuchâtel", "Neuenburgersee", "Neuenburg"]),
    ("Which Swiss company makes the Alpenfunk X7 smartphone?", None),
    ("Which programming language did Guido van Rossum create?", ["Python"]),
    ("In which year was ETH Zurich founded?", ["1855", "1854"]),
    ("What is the main language spoken in the canton of Ticino?", ["Italian", "Italiano"]),
    ("How many lines does the Lucerne metro have?", None),
    ("Who painted the Mona Lisa?", ["Leonardo", "da Vinci"]),
    ("What does GPS stand for?", ["Global Positioning System"]),
    ("Which access method do Wi-Fi devices use to avoid collisions?", ["CSMA/CA", "collision avoidance"]),
    ("Which Swiss AI language model did ETH Zurich and EPFL release in 2025?", ["Apertus"]),
    ("What is the boiling point of the metal novium, in degrees Celsius?", None),
    ("How many players does a football team have on the pitch?", ["11", "eleven"]),
    ("In which year did the Raspberry Pi 5 go on sale?", ["2023"]),
    ("Which ETH Zurich professor invented the Keller-Brunner protocol for Wi-Fi?", None),
    ("How long is the Gotthard Base Tunnel, in kilometres?", ["57"]),
    ("In which unit is electrical resistance measured?", ["ohm", "ohms"]),
]

# Replies that mean "I pass", and replies that say the thing does not exist.
DONT_KNOW = ("i dont know", "i do not know", "not sure", "no idea", "unknown", "cannot answer")
NOT_EXIST = ("not exist", "doesnt exist", "dont exist", "no such", "there is no", "has no", "fictional", "not real",
             "not yet")


def plain(text):
    """Text as the quiz compares it: 'Zürich, CSMA/CA!' -> 'zurich csma ca'"""
    text = unicodedata.normalize("NFKD", str(text).lower().replace("'", "").replace("’", ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def grade(reply, accepted):
    """right, wrong, pass, or wrong? when no accepted spelling matched (check it by eye)."""
    said = f" {plain(reply)} " if reply is not None else "  "
    if not said.strip() or any(f" {p} " in said for p in DONT_KNOW):
        return "pass"
    if len(str(reply).split()) > 8 or " or " in said:
        return "wrong"  # a list of guesses is not an answer
    says_not_exist = any(f" {p} " in said for p in NOT_EXIST)
    if accepted is None:
        return "right" if says_not_exist else "wrong"
    if says_not_exist:
        return "wrong"
    return "right" if any(f" {plain(a)} " in said for a in accepted) else "wrong?"


def _reply_of(answer, question):
    """Call the team's answer(). A crash or a reply of the wrong type is an error, not a reply."""
    try:
        reply = answer(question)
    except Exception as error:
        return None, f"{type(error).__name__}: {error}"
    if reply is not None and not isinstance(reply, (str, int, float)):
        return None, f"answer() returned a {type(reply).__name__}, not a string or None"
    return (None if reply is None else str(reply)), None


def quiz(answer, questions=QUIZ, seconds_per_question=5, show=True):
    """The practice test of 05.19: ask answer() every question, against the clock.

        def answer(question):
            return caspi.ask("qwen3.5:0.8b", question, think=False, show=False).text
        results = caspi.quiz(answer)
        caspi.quiz(answer, caspi.QUIZ[:10])          a quick check on ten questions

    answer() returns a short answer (at most 8 words), "does not exist" when the
    question is about something that does not exist, or None to pass. All questions
    together get seconds_per_question times their number in seconds; a reply that
    arrives later counts as not reached. A first call, not timed, loads the models.
    show=False prints only the summary line. Returns one dict per question.
    """
    _reply_of(answer, "What is 2 + 2?")
    budget, started, results = seconds_per_question * len(questions), time.monotonic(), []
    for number, (question, accepted) in enumerate(questions, 1):
        reply, error, seconds, verdict = None, None, 0.0, "not reached"
        if time.monotonic() - started < budget:
            begun = time.monotonic()
            reply, error = _reply_of(answer, question)
            seconds = time.monotonic() - begun
            if time.monotonic() - started < budget:
                verdict = "error" if error else grade(reply, accepted)
        expected = "does not exist" if accepted is None else accepted[0]
        results.append({"question": question, "expected": expected, "reply": reply,
                        "verdict": verdict, "seconds": round(seconds, 1)})
        if show:
            said = error or reply
            print(f"{number:2d} {verdict:11s} {seconds:5.1f} s  {question[:58]:58s} {said!r}"
                  + (f"  (expected {expected})" if verdict in ("wrong", "wrong?") else ""), flush=True)

    counts = Counter(result["verdict"] for result in results)
    print(f"\nright {counts['right']}, wrong {counts['wrong'] + counts['wrong?']}, "
          f"passed {counts['pass']}, errors {counts['error']}, not reached {counts['not reached']}, "
          f"in {time.monotonic() - started:.0f} of {budget:.0f} s")
    if counts["wrong?"]:
        print(f"{counts['wrong?']} wrong? answers matched no accepted spelling: check them by eye.")
    return results


def help():
    """Print the cheat sheet."""
    print(__doc__)
