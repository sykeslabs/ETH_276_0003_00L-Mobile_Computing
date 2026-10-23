from pathlib import Path
from html import escape
import base64
from IPython.display import display

def show_processor_animation(slug):
    folder = Path(__file__).resolve().parent
    document = (folder / f"{slug}.html").read_text(encoding="utf-8")
    height = 530 if slug == "npu-matrix-16x16" else 500
    frame = (f'<iframe title="{escape(slug)}" sandbox="allow-scripts" '
             f'style="width:100%;height:{height}px;border:1px solid #cbd5de;border-radius:8px" '
             f'srcdoc="{escape(document, quote=True)}"></iframe>')
    data = {"text/html": frame,
            "text/plain": f"Interactive animation: {folder / (slug + '.html')}"}
    snapshot = folder / f"{slug}.png"
    if snapshot.is_file():
        data["image/png"] = base64.b64encode(snapshot.read_bytes()).decode("ascii")
    display(data, raw=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("slug", choices=["cpu-matrix-16x16", "gpu-matrix-16x16", "npu-matrix-16x16"])
    show_processor_animation(parser.parse_args().slug)
