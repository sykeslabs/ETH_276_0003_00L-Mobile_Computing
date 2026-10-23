#!/usr/bin/env python3
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER_TEMPLATE = (ROOT / ".admin" / "header.md").read_text(newline="\n")
FOOTER_TEMPLATE = (ROOT / ".admin" / "footer.md").read_text(newline="\n")

HEADER_START = "<!-- header:start -->"
HEADER_END = "<!-- header:end -->"
FOOTER_START = "<!-- footer:start -->"
FOOTER_END = "<!-- footer:end -->"

HEADER_TARGETS = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "01_Lectures" / "README.md",
    ROOT / "02_Notebooks" / "README.md",
    ROOT / "02_Notebooks" / "Notebooks" / "00_Intro" / "GettingStarted.md",
    ROOT / "03_Assignments" / "Assignment-01.md",
    ROOT / "03_Assignments" / "Assignment-02.md",
    ROOT / "03_Assignments" / "Assignment-03.md",
    ROOT / "03_Assignments" / "Submission-Guidelines.md",
    ROOT / "03_Assignments" / "VlcSerial.md",
]

FOOTER_TARGETS = [ROOT / "README.md"] + [
    ROOT / "01_Lectures" / "README.md",
    ROOT / "02_Notebooks" / "README.md",
    ROOT / "02_Notebooks" / "Notebooks" / "00_Intro" / "GettingStarted.md",
    ROOT / "03_Assignments" / "Assignment-01.md",
    ROOT / "03_Assignments" / "Assignment-02.md",
    ROOT / "03_Assignments" / "Assignment-03.md",
    ROOT / "03_Assignments" / "Submission-Guidelines.md",
]


def relative_prefix(from_file: Path, to_dir: Path) -> str:
    rel = Path(os.path.relpath(to_dir, start=from_file.parent)).as_posix()
    if rel == ".":
        return ""
    return f"{rel}/"


def render_template(template: str, target: Path) -> str:
    assignments_prefix = relative_prefix(target, ROOT / "03_Assignments")
    lectures_prefix = relative_prefix(target, ROOT / "01_Lectures")
    notebooks_prefix = relative_prefix(target, ROOT / "02_Notebooks")
    root_prefix = relative_prefix(target, ROOT)
    return (
        template.replace("{{ASSIGNMENTS_PREFIX}}", assignments_prefix)
        .replace("{{LECTURES_PREFIX}}", lectures_prefix)
        .replace("{{NOTEBOOKS_PREFIX}}", notebooks_prefix)
        .replace("{{ROOT_PREFIX}}", root_prefix)
        .rstrip()
    )


def render_header(target: Path) -> str:
    return render_template(HEADER_TEMPLATE, target)


def render_footer(target: Path) -> str:
    return render_template(FOOTER_TEMPLATE, target)


def strip_existing_header(text: str) -> str:
    if HEADER_START in text and HEADER_END in text:
        before = text.split(HEADER_START, 1)[0]
        after = text.split(HEADER_END, 1)[1]
        return (before + after).lstrip()

    if text.startswith("[HOME]("):
        return text.split("\n", 1)[1].lstrip()

    if text.startswith("[Return HOME]("):
        return text.split("\n", 1)[1].lstrip()

    return text.lstrip()


def strip_existing_footer(text: str) -> str:
    if FOOTER_START in text and FOOTER_END in text:
        before = text.split(FOOTER_START, 1)[0]
        after = text.split(FOOTER_END, 1)[1]
        return (before + after).rstrip()

    legacy = "\n----\n<p align=\"center\">\n  <strong>Homework Assignments</strong><br>"
    if legacy in text:
        return text.split(legacy, 1)[0].rstrip()

    return text.rstrip()


def read_normalized(target: Path) -> tuple[str, str]:
    original = target.read_bytes()
    newline = "\r\n" if b"\r\n" in original else "\n"
    text = (
        original.decode()
        .replace("\r\r\n", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    return text, newline


def write_with_newline(target: Path, text: str, newline: str) -> None:
    target.write_bytes(text.replace("\n", newline).encode())


def update_header(target: Path) -> None:
    text, newline = read_normalized(target)
    header = render_header(target)
    body = strip_existing_header(text)
    updated = f"{HEADER_START}\n{header}\n{HEADER_END}\n\n{body.rstrip()}\n"
    write_with_newline(target, updated, newline)


def update_footer(target: Path) -> None:
    text, newline = read_normalized(target)
    footer = render_footer(target)
    updated = f"{strip_existing_footer(text)}\n\n{FOOTER_START}\n{footer}\n{FOOTER_END}\n"
    write_with_newline(target, updated, newline)


def main() -> None:
    touched = []
    for target in HEADER_TARGETS:
        update_header(target)
        touched.append(target)
    for target in FOOTER_TARGETS:
        update_footer(target)
        if target not in touched:
            touched.append(target)
    for target in touched:
        print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
