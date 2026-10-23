import getpass
import html
import json
import os
import urllib.error
import urllib.request

from IPython.display import HTML, Markdown, display
import ipywidgets as widgets


MODEL = "gpt-5.5"  # You may change this to another available OpenAI text model.
SYSTEM_PROMPT = """
You are a concise coding assistant for a Mobile Computing course.
Follow these rules:
1. Ask before assuming.
2. Use the simplest solution first.
3. Do not touch unrelated code.
4. Flag uncertainty explicitly.
Never ask students to paste secrets or private data.
""".strip()


def extract_output_text(response_data):
    if response_data.get("output_text"):
        return response_data["output_text"]

    parts = []
    for item in response_data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    return "\n".join(parts).strip()


def request_chatgpt(history, api_key):
    payload = {
        "model": MODEL,
        "instructions": SYSTEM_PROMPT,
        "input": history,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return extract_output_text(json.loads(response.read().decode("utf-8")))


def format_openai_error(status_code, details):
    try:
        error_data = json.loads(details).get("error", {})
    except json.JSONDecodeError:
        error_data = {}

    code = error_data.get("code")
    message = error_data.get("message") or details
    if status_code == 429 and code in {"insufficient_quota", "rate_limit_exceeded"}:
        return (
            "OpenAI API quota or rate limit exceeded. A ChatGPT Pro subscription does not "
            "automatically add API quota for this notebook. Check the API billing, project, "
            "and limits for the account that owns this API key at https://platform.openai.com/settings/organization/limits. "
            f"API message: {message}"
        )
    return f"Request failed ({status_code}): {message}"


def render_chat_line(speaker, text):
    return (
        '<div style="max-width: 100%; box-sizing: border-box; white-space: pre-wrap; '
        'overflow-wrap: anywhere; margin: 0 0 0.75em 0;">'
        f"<strong>{html.escape(speaker)}:</strong> {html.escape(text)}"
        "</div>"
    )


def display_chatgpt_dialog():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        api_key = getpass.getpass("OpenAI API key (hidden input, leave blank to skip): ").strip()

    if not api_key:
        display(Markdown("No API key provided. Use the suggested prompt above in ChatGPT instead."))
        return

    display(
        HTML(
            """
            <style>
            .mc-chat-panel,
            .mc-chat-panel .widget-box,
            .mc-chat-panel .widget-hbox,
            .mc-chat-panel .widget-vbox {
                background: transparent !important;
            }
            .mc-chat-output {
                max-height: 260px;
                overflow-y: auto !important;
                overflow-x: hidden !important;
            }
            </style>
            """
        )
    )

    conversation = []
    transcript = []
    prompt_box = widgets.Textarea(
        value="What should I check before accepting A.I.-generated code for a notebook exercise?",
        placeholder="Ask a short coding question...",
        description="",
        layout=widgets.Layout(width="100%", max_width="100%", height="100px"),
        style={"description_width": "0px"},
    )
    send_button = widgets.Button(description="Send", button_style="primary")
    clear_button = widgets.Button(description="Clear")
    buttons = widgets.HBox([send_button, clear_button], layout=widgets.Layout(background="transparent"))
    chat_output = widgets.HTML(
        value="",
        layout={
            "border": "1px solid #ddd",
            "padding": "8px",
            "width": "100%",
            "max_height": "260px",
            "overflow_y": "auto",
            "overflow_x": "hidden",
        }
    )
    panel = widgets.VBox([prompt_box, buttons, chat_output], layout=widgets.Layout(width="100%"))
    panel.add_class("mc-chat-panel")
    chat_output.add_class("mc-chat-output")

    def send_message(_):
        message = prompt_box.value.strip()
        if not message:
            return

        conversation.append({"role": "user", "content": message})
        transcript.append(("You", message))
        chat_output.value = "".join(render_chat_line(speaker, text) for speaker, text in transcript)
        prompt_box.value = ""
        send_button.disabled = True

        try:
            reply = request_chatgpt(conversation, api_key)
            conversation.append({"role": "assistant", "content": reply})
            transcript.append(("ChatGPT", reply))
            chat_output.value = "".join(render_chat_line(speaker, text) for speaker, text in transcript)
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            transcript.append(("Error", format_openai_error(error.code, details)))
            chat_output.value = "".join(render_chat_line(speaker, text) for speaker, text in transcript)
        except Exception as error:
            transcript.append(("Error", f"Request failed: {error}"))
            chat_output.value = "".join(render_chat_line(speaker, text) for speaker, text in transcript)
        finally:
            send_button.disabled = False

    def clear_chat(_):
        conversation.clear()
        transcript.clear()
        chat_output.value = ""

    send_button.on_click(send_message)
    clear_button.on_click(clear_chat)
    display(panel)
