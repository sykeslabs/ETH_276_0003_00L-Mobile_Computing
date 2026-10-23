"""Reusable notebook PDF presentation viewer.

Call show_pdf(pdf_path) to install missing dependencies and display
an independent viewer. Relative PDF paths are resolved against the kernel's
working directory. Existing dependencies produce no installation output.
"""

import base64
import json
import os
import tempfile
from pathlib import Path
from html import escape


def show_pdf(pdf_path, notes_path=None):
    """Display slides with autosaved per-page notes.

    Notes default to <PDF stem>.notes.json beside the PDF. Pass notes_path
    to select another local file. Saving requires an active notebook kernel.
    """
    pdf_path = Path(pdf_path).expanduser().resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    import importlib.util
    import subprocess
    import sys

    required_packages = {"pymupdf": "pymupdf", "ipywidgets": "ipywidgets"}
    missing_packages = [
        package for module, package in required_packages.items()
        if importlib.util.find_spec(module) is None
    ]
    if missing_packages:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", *missing_packages
        ])

    importlib.invalidate_caches()
    import ipywidgets as widgets
    import pymupdf
    from IPython.display import display

    with pymupdf.open(pdf_path) as document:
        total_pages = document.page_count
    if total_pages == 0:
        raise ValueError("The selected PDF contains no pages.")

    initial_pdf = pdf_path
    custom_notes_path = Path(notes_path).expanduser().resolve() if notes_path is not None else None
    # A sidecar beside the PDF keeps notes consistent across notebooks.
    notes_path = (
        Path(notes_path).expanduser().resolve() if notes_path is not None
        else pdf_path.with_suffix(".notes.json")
    )

    def read_notes(path=None):
        path = notes_path if path is None else path
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in data.items()
        ):
            raise ValueError(f"Invalid notes file: {path}")
        return data

    notes = read_notes()
    notes_editor = widgets.Textarea(
        placeholder="Your notes for this slide ...",
        continuous_update=True,
        layout=widgets.Layout(
            width="auto", height="auto", min_height="0", min_width="0",
            align_self="stretch", flex="1 1 0", margin="0 0 0 2%",
        ),
    )
    notes_editor.add_class("lecture-pdf-notes-input")
    notes_editor.layout.margin = "0"
    notes_editor.layout.width = "100%"
    notes_footer = widgets.HTML(layout=widgets.Layout(width="100%", margin="0"))
    notes_footer.add_class("lecture-pdf-notes-footer")
    notes_paper = widgets.VBox(
        [notes_editor, notes_footer],
        layout=widgets.Layout(width="auto", min_width="0", min_height="0",
                              flex="1 1 0", margin="0 0 0 2%", align_self="stretch"),
    )
    notes_paper.add_class("lecture-pdf-notes")
    notes_paper.layout.margin = "0"
    notes_paper.layout.width = "100%"
    notes_paper.layout.height = "100%"
    old_sheet = widgets.HTML(layout=widgets.Layout(margin="0", width="100%", height="100%"))
    old_sheet.add_class("lecture-pdf-old-sheet-layer")
    notes_viewport = widgets.Box(
        [notes_paper, old_sheet],
        layout=widgets.Layout(width="auto", min_width="0", min_height="0",
                              flex="1 1 0", margin="0 0 0 2%", align_self="stretch"),
    )
    notes_viewport.add_class("lecture-pdf-paper-viewport")
    notes_style = widgets.HTML(
        value="<style>" + (Path(__file__).with_suffix(".css").read_text(encoding="utf-8")
                          + Path(__file__).with_name("viewer_background.css").read_text(encoding="utf-8")) + "</style>",
        layout=widgets.Layout(display="none"),
    )
    save_status = widgets.Label(layout=widgets.Layout(display="none"))
    loading_notes = False
    active_page = 1
    paper_motion = False

    def save_notes(change):
        nonlocal loading_notes
        if loading_notes:
            return
        text = change["new"]
        if not text.strip():
            text = ""
            if notes_editor.value:
                loading_notes = True
                try:
                    notes_editor.value = ""
                finally:
                    loading_notes = False
        temporary_path = None
        try:
            # Merge other pages from disk before replacing this page's notes.
            latest = read_notes()
            latest[str(active_page)] = text
            notes_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=notes_path.parent,
                prefix=notes_path.name + ".", suffix=".tmp", delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(latest, temporary, ensure_ascii=False, indent=2)
                temporary.write("\n")
            os.replace(temporary_path, notes_path)
            notes.clear()
            notes.update(latest)
            save_status.value = ""
            save_status.layout.display = "none"
        except (OSError, ValueError) as error:
            save_status.value = f"Notes not saved: {error}"
            save_status.layout.display = ""
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    notes_editor.observe(save_notes, names="value")

    previous_button = widgets.Button(description="Previous", icon="chevron-left")
    next_button = widgets.Button(description="Next", icon="chevron-right")
    page_number = widgets.BoundedIntText(
        value=1, min=1, max=total_pages,
        description="Page:", layout=widgets.Layout(width="160px"),
    )
    page_number.add_class('lecture-pdf-page-selector')
    page_count = widgets.Label(value=f"of {total_pages}")
    page_count.add_class('lecture-pdf-page-count')
    pdf_files = sorted(
        (path for path in pdf_path.parent.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: path.name.casefold(),
    )
    lecture_picker = widgets.Dropdown(
        options=[(path.name, str(path)) for path in pdf_files], value=str(pdf_path),
        description="Lecture:", layout=widgets.Layout(width="100%", min_width="0", margin="0"),
    )
    lecture_picker.add_class("lecture-pdf-picker")
    saved_pages = {}
    switching_lecture = False
    slide = widgets.Image(
        format="png",
        layout=widgets.Layout(width="100%", max_width="100%", min_width="0"),
    )


    def render_page(change=None):
        nonlocal loading_notes, active_page, paper_motion
        previous_text = notes_editor.value
        previous_footer = notes_footer.value
        with pymupdf.open(pdf_path) as document:
            page = document.load_page(page_number.value - 1)
            # Keep rendering resolution independent of the displayed percentage.
            scale = 2400 / page.rect.width
            slide.value = page.get_pixmap(
                matrix=pymupdf.Matrix(scale, scale), alpha=False
            ).tobytes("png")
        if change is None or active_page != page_number.value:
            active_page = page_number.value
            loading_notes = True
            try:
                text = notes.get(str(active_page), "")
                notes_editor.value = text if text.strip() else ""
            finally:
                loading_notes = False

        notes_footer.value = (
            f'<span class="lecture-pdf-notes-filename">{escape(pdf_path.name)}</span>'
            f'<span class="lecture-pdf-notes-page">Page {page_number.value} / {total_pages}</span>'
        )
        if change is not None:
            forward = change["new"] > change["old"]
            notes_viewport.remove_class("lecture-paper-backward" if forward else "lecture-paper-forward")
            notes_viewport.add_class("lecture-paper-forward" if forward else "lecture-paper-backward")
            old_sheet.value = (
                '<div class="lecture-pdf-notes lecture-pdf-outgoing-sheet">'
                f'<pre class="lecture-pdf-old-notes">{escape(previous_text)}</pre>'
                '<div class="lecture-pdf-notes-footer"><div class="widget-html-content">'
                + previous_footer + '</div></div></div>'
            )
            paper_motion = not paper_motion
            notes_paper.remove_class("lecture-paper-motion-b" if paper_motion else "lecture-paper-motion-a")
            notes_paper.add_class("lecture-paper-motion-a" if paper_motion else "lecture-paper-motion-b")
        else:
            old_sheet.value = ""
            notes_paper.remove_class("lecture-paper-motion-a")
            notes_paper.remove_class("lecture-paper-motion-b")
        previous_button.disabled = page_number.value == 1
        next_button.disabled = page_number.value == total_pages


    def select_lecture(change):
        nonlocal pdf_path, notes_path, total_pages, active_page, switching_lecture
        if switching_lecture:
            return
        candidate = Path(change["new"])
        if candidate == pdf_path:
            return
        switching_lecture = True
        try:
            # Validate the destination before replacing the current slide or notes.
            with pymupdf.open(candidate) as document:
                count = document.page_count
            if not count:
                raise ValueError("The selected PDF contains no pages.")
            candidate_notes = (custom_notes_path if candidate == initial_pdf and custom_notes_path
                               else candidate.with_suffix(".notes.json"))
            incoming_notes = read_notes(candidate_notes)
            save_notes({"new": notes_editor.value})
            if save_status.value:
                raise OSError(save_status.value)
            saved_pages[pdf_path] = page_number.value
            pdf_path, notes_path, total_pages = candidate, candidate_notes, count
            notes.clear()
            notes.update(incoming_notes)
            # Avoid rendering mid-update when the new PDF has a different page count.
            page_number.unobserve(render_page, names="value")
            try:
                page_number.max = count
                page_number.value = min(saved_pages.get(candidate, 1), count)
            finally:
                page_number.observe(render_page, names="value")
            page_count.value = f"of {count}"
            render_page()
            save_status.value = ""
            save_status.layout.display = "none"
        except (OSError, ValueError, RuntimeError) as error:
            lecture_picker.value = str(pdf_path)
            save_status.value = f"Could not open lecture: {error}"
            save_status.layout.display = ""
        finally:
            switching_lecture = False

    lecture_picker.observe(select_lecture, names="value")

    def previous_page(button):
        page_number.value = max(1, page_number.value - 1)


    def next_page(button):
        page_number.value = min(total_pages, page_number.value + 1)


    previous_button.on_click(previous_page)
    next_button.on_click(next_page)
    page_number.observe(render_page, names="value")
    slide.layout.width = "100%"
    slide_panel = widgets.VBox(
        [slide], layout=widgets.Layout(
            width="auto", min_width="0", flex="1 1 0", margin="0",
            overflow="hidden",
        ),
    )
    slide_panel.add_class("lecture-pdf-screen")
    logo_path = Path(__file__).resolve().parents[2] / "img/eth_logo.png"
    logo_html = (
        '<img alt="ETH Zürich" src="data:image/png;base64,'
        + base64.b64encode(logo_path.read_bytes()).decode() + '">'
        if logo_path.exists() else '<strong>ETH Zürich</strong>'
    )
    logo = widgets.HTML(logo_html, layout=widgets.Layout(
        width="110px", min_width="110px", margin="0 0 0 auto",
    ))
    logo.add_class("lecture-pdf-logo")
    for control in (previous_button, next_button, page_number, page_count, logo):
        control.layout.height = "36px"
        control.layout.align_self = "center"
        if control is not logo:
            control.layout.margin = "0 4px"
    controls = widgets.HBox(
        [previous_button, next_button, page_number, page_count, logo],
        layout=widgets.Layout(align_items="center"),
    )
    controls.add_class("lecture-pdf-controls")
    render_page()
    viewer = widgets.VBox([
        notes_style,
        controls,
        lecture_picker,
        widgets.HBox(
            [slide_panel, notes_viewport],
            layout=widgets.Layout(
                width="100%", max_width="100%", overflow="hidden",
                justify_content="center",
                align_items="stretch", flex_flow="row nowrap",
            ),
        ),
        save_status,
    ], layout=widgets.Layout(width="100%", max_width="100%"))
    viewer.add_class("lecture-pdf-machine")
    display(viewer)
