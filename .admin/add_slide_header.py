#!/usr/bin/env python3

import argparse
import base64
import html
import json
import re
from pathlib import Path


START_MARKER = "<!-- course-slide-header:start -->"
END_MARKER = "<!-- course-slide-header:end -->"


def data_uri(path: Path, media_type: str) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def notebook_title(path: Path) -> str:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue
        source = "".join(cell.get("source", []))
        for line in source.splitlines():
            text = re.sub(r"^\s*#{1,6}\s*", "", line).strip()
            if not text:
                continue
            text = re.sub(r"(\*\*|__|`)", "", text).strip()
            return text
    return path.stem.replace("_", " ")


def title_html(title: str) -> str:
    match = re.match(r"^(Hands[\s-]On Exercise:)\s*(.*)$", title, re.IGNORECASE)
    if match:
        prefix = html.escape(match.group(1))
        remainder = html.escape(match.group(2))
        return f"<strong>{prefix}</strong> {remainder}"
    return html.escape(title)


def build_header(
    title: str,
    logo_uri: str,
    regular_font_uri: str,
    bold_font_uri: str,
) -> str:
    safe_title = title_html(title)
    return f"""{START_MARKER}
<style>
@font-face {{
  font-family: "CourseRoboto";
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url("{regular_font_uri}") format("truetype");
}}
@font-face {{
  font-family: "CourseRoboto";
  font-style: normal;
  font-weight: 700;
  font-display: swap;
  src: url("{bold_font_uri}") format("truetype");
}}
.reveal .slides section {{
  box-sizing: border-box;
  padding-top: 4em !important;
}}
.reveal .slides section.present:not(.stack) {{
  height: 100%;
  max-height: 100%;
  overflow-x: hidden;
  overflow-y: scroll !important;
  overscroll-behavior-y: contain;
  scrollbar-gutter: stable;
  scrollbar-color: #b3313b rgba(179, 49, 59, 0.16);
  scrollbar-width: auto;
}}
.reveal .slides section.present:not(.stack)::-webkit-scrollbar {{
  width: 14px;
}}
.reveal .slides section.present:not(.stack)::-webkit-scrollbar-track {{
  background: rgba(179, 49, 59, 0.16);
  border-radius: 7px;
}}
.reveal .slides section.present:not(.stack)::-webkit-scrollbar-thumb {{
  min-height: 48px;
  background: #b3313b;
  border: 3px solid rgba(255, 255, 255, 0.7);
  border-radius: 7px;
}}
.reveal .celltag_hide-widget-repr
  .jp-RenderedText[data-mime-type="text/plain"] {{
  display: none !important;
}}
#course-slide-header {{
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  box-sizing: border-box;
  min-height: 112px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  padding: 12px 18px;
  background: #b3313b;
  color: #e8eef0;
  font-family: "CourseRoboto", sans-serif !important;
  font-size: 28px;
  line-height: 1.2;
  text-align: right;
  pointer-events: none;
}}
#course-slide-header * {{
  font-family: "CourseRoboto", sans-serif !important;
}}
#course-slide-header .eth-logo {{
  position: fixed;
  top: 12px;
  left: 18px;
  z-index: 1001;
  display: block;
  width: 240px;
  height: auto;
  filter: brightness(0) saturate(100%) invert(97%) sepia(5%) saturate(240%)
    hue-rotate(153deg) brightness(97%) contrast(93%);
}}
</style>
<div id="course-slide-header" aria-label="Presentation header">
  <div><strong>Mobile Computing</strong></div>
  <div>{safe_title}</div>
  <img class="eth-logo" src="{logo_uri}" alt="ETH Zurich logo">
</div>
{END_MARKER}"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inject the shared Mobile Computing header into nbconvert slides."
    )
    parser.add_argument("--notebook", required=True, type=Path)
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--logo", required=True, type=Path)
    parser.add_argument("--font-regular", required=True, type=Path)
    parser.add_argument("--font-bold", required=True, type=Path)
    args = parser.parse_args()

    html_text = args.html.read_text(encoding="utf-8")
    html_text = re.sub(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        "",
        html_text,
        flags=re.DOTALL,
    )

    header = build_header(
        notebook_title(args.notebook),
        data_uri(args.logo, "image/png"),
        data_uri(args.font_regular, "font/ttf"),
        data_uri(args.font_bold, "font/ttf"),
    )

    if "</body>" not in html_text:
        raise ValueError(f"Could not find </body> in {args.html}")

    html_text = html_text.replace("</body>", f"{header}\n</body>", 1)
    args.html.write_text(html_text, encoding="utf-8")


if __name__ == "__main__":
    main()
