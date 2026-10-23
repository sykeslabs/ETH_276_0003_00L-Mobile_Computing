"""Generate the SaaS/PaaS/IaaS responsibility-stack diagram."""

from html import escape
from pathlib import Path


WIDTH, HEIGHT = 1500, 770
OUTPUT = Path(__file__).with_suffix(".svg")


def text(x, y, value, *, size=22, weight=400, anchor="start", fill="#18324A"):
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}">{escape(value)}</text>'
    )


def cell(x, y, w, h, owner, detail=""):
    consumer = owner == "Consumer"
    fill = "#FFF0DE" if consumer else "#E8F1FF"
    stroke = "#E49A3A" if consumer else "#4B78C2"
    result = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="2"/>']
    result.append(text(x + w / 2, y + 31, owner, size=20, weight=500, anchor="middle", fill="#18324A"))
    if detail:
        result.append(text(x + w / 2, y + 55, detail, size=16, anchor="middle", fill="#56697C"))
    return "".join(result)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        "Data and application settings",
        "Application",
        "Runtime and libraries",
        "Operating system",
        "Virtualization",
        "Servers and storage hardware",
        "Network and datacenter",
    ]
    columns = [
        ("SaaS", [("Consumer", "limited settings"), ("Provider", ""), ("Provider", ""), ("Provider", ""), ("Provider", ""), ("Provider", ""), ("Provider", "")]),
        ("PaaS", [("Consumer", ""), ("Consumer", ""), ("Provider", "supported tools"), ("Provider", ""), ("Provider", ""), ("Provider", ""), ("Provider", "")]),
        ("IaaS", [("Consumer", ""), ("Consumer", ""), ("Consumer", ""), ("Consumer", ""), ("Provider", ""), ("Provider", ""), ("Provider", "")]),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        '<title id="title">Control and responsibility across cloud service models</title>',
        '<desc id="desc">A layer stack showing which layers are managed by the consumer or provider in SaaS, PaaS, and IaaS.</desc>',
    ]
    label_x, start_x, start_y = 55, 420, 90
    col_w, gap, row_h, row_gap = 320, 24, 72, 10
    for index, row in enumerate(rows):
        y = start_y + index * (row_h + row_gap)
        parts.append(text(label_x, y + 42, row, size=20, weight=500))
    for col_index, (name, ownership) in enumerate(columns):
        x = start_x + col_index * (col_w + gap)
        parts.append(text(x + col_w / 2, 65, name, size=28, weight=500, anchor="middle"))
        for row_index, (owner, detail) in enumerate(ownership):
            y = start_y + row_index * (row_h + row_gap)
            parts.append(cell(x, y, col_w, row_h, owner, detail))
    parts.extend(
        [
            '<rect x="410" y="675" width="26" height="26" rx="5" fill="#FFF0DE" stroke="#E49A3A" stroke-width="2"/>',
            text(448, 696, "Managed by consumer", size=19),
            '<rect x="680" y="675" width="26" height="26" rx="5" fill="#E8F1FF" stroke="#4B78C2" stroke-width="2"/>',
            text(718, 696, "Managed by provider", size=19),
            text(750, 748, "Physical infrastructure remains with the provider in all three models.", size=21, weight=500, anchor="middle", fill="#42566A"),
            '</svg>',
        ]
    )
    OUTPUT.write_text("".join(parts), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
