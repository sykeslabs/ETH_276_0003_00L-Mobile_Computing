#!/usr/bin/env python3

import argparse
import asyncio
import base64
import html
import json
import re
from pathlib import Path


def data_uri(path: Path, media_type: str) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def notebook_title(path: Path) -> str:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue
        for line in "".join(cell.get("source", [])).splitlines():
            title = re.sub(r"^\s*#{1,6}\s*", "", line).strip()
            if title:
                return re.sub(r"(\*\*|__|`)", "", title).strip()
    return path.stem.replace("_", " ")


def inject_print_css(document: str, regular_font_uri: str, bold_font_uri: str) -> str:
    css = f"""
<style id="course-handout-print-style">
@font-face {{
  font-family: "CourseRoboto";
  font-weight: 400;
  src: url("{regular_font_uri}") format("truetype");
}}
@font-face {{
  font-family: "CourseRoboto";
  font-weight: 700;
  src: url("{bold_font_uri}") format("truetype");
}}
@page {{ size: A4 portrait; }}
html, body {{
  font-family: "CourseRoboto", Arial, sans-serif !important;
  font-size: 10pt !important;
  line-height: 1.35 !important;
}}
body {{ margin: 0 !important; }}
.jp-Notebook, main {{ max-width: none !important; padding: 0 !important; }}
.jp-Cell {{ break-inside: avoid; page-break-inside: avoid; }}
.jp-Cell-inputWrapper, .jp-Cell-outputWrapper {{ overflow: visible !important; }}
pre {{ white-space: pre-wrap !important; overflow-wrap: anywhere; font-size: 8pt !important; }}
img, svg, canvas {{ max-width: 100% !important; height: auto !important; }}
table {{ font-size: 8.5pt !important; }}
h1, h2, h3, h4 {{ break-after: avoid; page-break-after: avoid; }}
</style>
"""
    if "</head>" not in document:
        raise ValueError("The generated HTML has no </head> element")
    return document.replace("</head>", f"{css}</head>", 1)


async def render(args: argparse.Namespace) -> None:
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright is required. Install it with: "
            "python3 -m pip install 'nbconvert[webpdf]'"
        ) from exc

    document = args.html.read_text(encoding="utf-8")
    document = inject_print_css(
        document,
        data_uri(args.font_regular, "font/ttf"),
        data_uri(args.font_bold, "font/ttf"),
    )
    printable_html = args.html.with_suffix(".handout.html")
    printable_html.write_text(document, encoding="utf-8")

    title = html.escape(notebook_title(args.notebook))
    filename = html.escape(args.pdf.name)
    logo = data_uri(args.logo, "image/png")

    header = f"""
<div style="width:100%; height:21mm; box-sizing:border-box; padding:4mm 10mm;
            background:#b3313b; color:#e8eef0; font-family:Arial,sans-serif;
            display:flex; align-items:center; justify-content:space-between;">
  <img src="{logo}" style="width:34mm; filter:brightness(0) invert(1);">
  <div style="text-align:right; line-height:1.25; font-size:9pt;">
    <strong style="font-size:11pt;">Mobile Computing</strong><br>{title}
  </div>
</div>
"""
    footer = f"""
<div style="width:100%; height:39mm; box-sizing:border-box; padding:1mm 10mm 3mm;
            color:#4a4a4a; font-family:Arial,sans-serif; font-size:8pt;">
  <div style="font-weight:bold; margin-bottom:1mm;">Notes</div>
  <div style="height:7mm; border-bottom:0.25mm solid #b9b9b9;"></div>
  <div style="height:7mm; border-bottom:0.25mm solid #b9b9b9;"></div>
  <div style="height:7mm; border-bottom:0.25mm solid #b9b9b9;"></div>
  <div style="display:flex; justify-content:space-between; margin-top:2mm;">
    <span>{filename}</span>
    <span>Page <span class="pageNumber"></span> / <span class="totalPages"></span></span>
  </div>
</div>
"""

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.emulate_media(media="print")
        await page.goto(printable_html.resolve().as_uri(), wait_until="networkidle")
        await page.pdf(
            path=str(args.pdf),
            format="A4",
            landscape=False,
            print_background=True,
            display_header_footer=True,
            header_template=header,
            footer_template=footer,
            margin={"top": "25mm", "right": "12mm", "bottom": "43mm", "left": "12mm"},
            prefer_css_page_size=True,
        )
        await browser.close()
    finally:
        await playwright.stop()
        printable_html.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an A4 Mobile Computing PDF handout.")
    parser.add_argument("--notebook", required=True, type=Path)
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--logo", required=True, type=Path)
    parser.add_argument("--font-regular", required=True, type=Path)
    parser.add_argument("--font-bold", required=True, type=Path)
    args = parser.parse_args()
    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    try:
        asyncio.run(render(args))
    except Exception as exc:
        raise SystemExit(f"Error: {exc}") from None


if __name__ == "__main__":
    main()
