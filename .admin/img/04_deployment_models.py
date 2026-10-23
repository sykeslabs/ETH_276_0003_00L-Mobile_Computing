"""Generate a four-panel comparison of cloud deployment models."""

from html import escape
from pathlib import Path


WIDTH, HEIGHT = 1400, 750
OUTPUT = Path(__file__).with_suffix(".svg")


def text(x, y, value, *, size=22, weight=400, anchor="start", fill="#18324A"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(value)}</text>'


def rect(x, y, w, h, *, fill="#FFFFFF", stroke="#B9C5D1", radius=20, dash=""):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash_attr}/>'


def circle(x, y, label, color="#E8F1FF"):
    return "".join([
        f'<circle cx="{x}" cy="{y}" r="31" fill="{color}" stroke="#4B78C2" stroke-width="2"/>',
        text(x, y + 7, label, size=17, weight=500, anchor="middle"),
    ])


def cloud(x, y, w, h, label, color="#DDF5EE"):
    return "".join([
        rect(x, y, w, h, fill=color, stroke="#28A58C", radius=30),
        text(x + w / 2, y + h / 2 + 7, label, size=20, weight=500, anchor="middle"),
    ])


def arrow(x1, y1, x2, y2, *, color="#6F8192", dash=""):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="3" marker-end="url(#arrow)"{dash_attr}/>'


def panel(x, y, title, subtitle):
    return "".join([
        rect(x, y, 620, 325, fill="#FFFFFF", stroke="#D4DDE6", radius=24),
        text(x + 26, y + 42, title, size=27, weight=500),
        text(x + 26, y + 70, subtitle, size=18, fill="#5D7083"),
    ])


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif" width="{WIDTH}" height="{HEIGHT}" viewBox="0 95 {WIDTH} {HEIGHT}" role="img" aria-describedby="desc">',
        '<desc id="desc">Public, private, community, and hybrid cloud topologies compared in four panels.</desc>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#6F8192"/></marker></defs>',
        panel(55, 120, "Public cloud", "Open use through a cloud provider"),
        panel(725, 120, "Private cloud", "Exclusive use by one organization"),
        panel(55, 485, "Community cloud", "Shared requirements and governance"),
        panel(725, 485, "Hybrid cloud", "Distinct clouds connected together"),
    ]
    # Public cloud
    for cy, label in [(235, "A"), (305, "B"), (375, "C")]:
        parts.append(circle(155, cy, f"Org {label}"))
        parts.append(arrow(190, cy, 370, 305))
    parts.append(cloud(385, 235, 225, 140, "Provider cloud"))
    parts.append(text(497, 403, "Unrelated consumers share pooled resources", size=17, anchor="middle", fill="#5D7083"))
    # Private cloud
    parts.append(rect(785, 205, 500, 200, fill="#F4F7FB", stroke="#6D5BD0", radius=18, dash="8 6"))
    parts.append(text(805, 232, "Organization boundary", size=17, weight=500, fill="#6D5BD0"))
    parts.append(circle(860, 300, "Dept A", color="#F0ECFF"))
    parts.append(circle(860, 365, "Dept B", color="#F0ECFF"))
    parts.append(arrow(895, 300, 1035, 315))
    parts.append(arrow(895, 365, 1035, 335))
    parts.append(cloud(1050, 270, 200, 110, "Private cloud", color="#EEE9FF"))
    # Community cloud
    for cx, cy, label in [(155, 640, "Univ A"), (155, 735, "Univ B"), (360, 775, "Univ C")]:
        parts.append(circle(cx, cy, label, color="#FFF0DE"))
        parts.append(arrow(cx + 35, cy, 410, 690))
    parts.append(cloud(420, 620, 220, 145, "Community cloud", color="#FFF0DE"))
    # Hybrid cloud
    parts.append(cloud(785, 625, 205, 130, "Private cloud", color="#EEE9FF"))
    parts.append(cloud(1135, 625, 205, 130, "Public cloud"))
    parts.append(arrow(1000, 675, 1125, 675, color="#D66A3A", dash="10 7"))
    parts.append(arrow(1125, 715, 1000, 715, color="#D66A3A", dash="10 7"))
    parts.append(text(1062, 648, "Cloud bursting", size=18, weight=500, anchor="middle", fill="#B4522C"))
    parts.append(text(1062, 790, "Data and applications move through compatible interfaces", size=17, anchor="middle", fill="#5D7083"))
    parts.append('</svg>')
    OUTPUT.write_text("".join(parts), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
