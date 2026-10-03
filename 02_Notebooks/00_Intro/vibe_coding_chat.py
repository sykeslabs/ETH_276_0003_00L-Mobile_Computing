import getpass
import html
import json
import os
import urllib.error
import urllib.request

from IPython.display import HTML, Markdown, display
import ipywidgets as widgets


OPENROUTER_MODEL = "anthropic/claude-sonnet-4.5"

SYSTEM_PROMPT = """
You are a concise coding assistant for a Mobile Computing course.
Follow these rules:
1. Ask before assuming.
2. Use the simplest solution first.
3. Do not touch unrelated code.
4. Flag uncertainty explicitly.
Never ask students to paste secrets or private data.
""".strip()


def request_openrouter(history, api_key):
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    messages.extend(history)

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
    }

    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))

    return data["choices"][0]["message"]["content"]


def render_chat_line(speaker, text):
    return (
        '<div style="max-width: 100%; box-sizing: border-box; '
        'white-space: pre-wrap; overflow-wrap: anywhere; '
        'margin: 0 0 0.75em 0;">'
        f"<strong>{html.escape(speaker)}:</strong> "
        f"{html.escape(text)}"
        "</div>"
    )


def display_chat_dialog():
    api_key = os.environ.get("OPENROUTER_API_KEY")

    if not api_key:
        api_key = getpass.getpass(
            "OpenRouter API key: "
        ).strip()

    if not api_key:
        display(
            Markdown(
                "No OpenRouter API key provided."
            )
        )
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
        value=(
            "What should I check before accepting "
            "A.I.-generated code for a notebook exercise?"
        ),
        placeholder="Ask a short coding question...",
        description="",
        layout=widgets.Layout(
            width="100%",
            max_width="100%",
            height="100px"
        ),
        style={"description_width": "0px"},
    )

    send_button = widgets.Button(
        description="Send",
        button_style="primary"
    )

    clear_button = widgets.Button(
        description="Clear"
    )

    buttons = widgets.HBox(
        [send_button, clear_button],
        layout=widgets.Layout(
            background="transparent"
        )
    )

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

    panel = widgets.VBox(
        [
            prompt_box,
            buttons,
            chat_output
        ],
        layout=widgets.Layout(width="100%")
    )

    panel.add_class("mc-chat-panel")
    chat_output.add_class("mc-chat-output")

    def send_message(_):
        message = prompt_box.value.strip()

        if not message:
            return

        # Add user message to conversation
        conversation.append(
            {
                "role": "user",
                "content": message
            }
        )

        transcript.append(
            ("You", message)
        )

        chat_output.value = "".join(
            render_chat_line(speaker, text)
            for speaker, text in transcript
        )

        prompt_box.value = ""
        send_button.disabled = True

        try:
            # Send conversation to Claude via OpenRouter
            reply = request_openrouter(
                conversation,
                api_key
            )

            # Add Claude's response to conversation
            conversation.append(
                {
                    "role": "assistant",
                    "content": reply
                }
            )

            transcript.append(
                (
                    "Claude via OpenRouter",
                    reply
                )
            )

            # IMPORTANT:
            # Refresh the displayed chat after receiving the response
            chat_output.value = "".join(
                render_chat_line(speaker, text)
                for speaker, text in transcript
            )

        except urllib.error.HTTPError as error:
            details = error.read().decode(
                "utf-8",
                errors="replace"
            )

            try:
                error_data = json.loads(details)
                error_message = (
                    error_data
                    .get("error", {})
                    .get("message", details)
                )
            except json.JSONDecodeError:
                error_message = details

            transcript.append(
                (
                    "Error",
                    f"OpenRouter request failed "
                    f"({error.code}): {error_message}"
                )
            )

            chat_output.value = "".join(
                render_chat_line(speaker, text)
                for speaker, text in transcript
            )

        except Exception as error:
            transcript.append(
                (
                    "Error",
                    f"Request failed: {error}"
                )
            )

            chat_output.value = "".join(
                render_chat_line(speaker, text)
                for speaker, text in transcript
            )

        finally:
            send_button.disabled = False

    def clear_chat(_):
        conversation.clear()
        transcript.clear()
        chat_output.value = ""

    send_button.on_click(send_message)
    clear_button.on_click(clear_chat)

    display(panel)