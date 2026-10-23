"""Generate the end-to-end image-processing cloud architecture."""

from html import escape
from pathlib import Path


WIDTH, HEIGHT = 1600, 750
OUTPUT = Path(__file__).with_suffix(".svg")


def text(x, y, value, *, size=22, weight=400, anchor="start", fill="#18324A"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(value)}</text>'


def node(x, y, w, h, title, subtitle="", *, fill="#FFFFFF", stroke="#4B78C2"):
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="20" fill="{fill}" stroke="{stroke}" stroke-width="3"/>',
        text(x + w / 2, y + 42, title, size=23, weight=500, anchor="middle"),
    ]
    if subtitle:
        parts.append(text(x + w / 2, y + 72, subtitle, size=17, anchor="middle", fill="#5D7083"))
    return "".join(parts)


def arrow(x1, y1, x2, y2, label="", *, color="#2F6BFF", dash="", label_y=-12):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    parts = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="4" marker-end="url(#arrow-{color[1:]})"{dash_attr}/>']
    if label:
        parts.append(text((x1 + x2) / 2, (y1 + y2) / 2 + label_y, label, size=17, weight=500, anchor="middle", fill=color))
    return "".join(parts)


def path_arrow(d, label_x, label_y, label, *, color="#2F6BFF", dash=""):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return "".join([
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="4" marker-end="url(#arrow-{color[1:]})"{dash_attr}/>',
        text(label_x, label_y, label, size=17, weight=500, anchor="middle", fill=color),
    ])


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif" width="{WIDTH}" height="{HEIGHT}" viewBox="0 105 {WIDTH} {HEIGHT}" role="img" aria-describedby="desc">',
        '<desc id="desc">The synchronous upload path and asynchronous processing path through the cloud application.</desc>',
        '<defs>',
        '<marker id="arrow-2F6BFF" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#2F6BFF"/></marker>',
        '<marker id="arrow-D66A3A" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#D66A3A"/></marker>',
        '<marker id="arrow-28A58C" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#28A58C"/></marker>',
        '</defs>',
        '<rect x="245" y="125" width="1305" height="650" rx="30" fill="#FFFFFF" stroke="#A8B8C7" stroke-width="3" stroke-dasharray="10 8"/>',
        text(275, 163, "Cloud application boundary", size=20, weight=500, fill="#5D7083"),
        node(45, 265, 155, 100, "Client", "uploads image", fill="#FFF0DE", stroke="#E49A3A"),
        node(285, 265, 205, 100, "Public endpoint", "DNS + HTTPS"),
        node(555, 265, 205, 100, "Load balancer", "selects API instance"),
        node(825, 265, 190, 100, "API", "validates + creates job"),
        node(1090, 265, 190, 100, "Work queue", "stores pending jobs", fill="#FFF0DE", stroke="#D66A3A"),
        node(1350, 265, 155, 100, "Workers", "process images", fill="#FFF0DE", stroke="#D66A3A"),
        node(780, 555, 240, 105, "Input storage", "original images", fill="#E8F7F3", stroke="#28A58C"),
        node(1285, 555, 250, 105, "Result storage", "processed images", fill="#E8F7F3", stroke="#28A58C"),
        arrow(200, 315, 275, 315, "HTTPS", label_y=-16),
        arrow(490, 315, 545, 315),
        arrow(760, 315, 815, 315),
        arrow(1015, 315, 1080, 315, "enqueue", color="#D66A3A", dash="10 7", label_y=-16),
        arrow(1280, 315, 1340, 315, "consume", color="#D66A3A", dash="10 7", label_y=-16),
        arrow(920, 375, 900, 545, "store image", color="#28A58C", label_y=-8),
        arrow(1428, 375, 1415, 545, "write result", color="#28A58C", label_y=-8),
        path_arrow('M 1350 345 C 1220 470, 1080 505, 1020 600', 1170, 485, "load original", color="#28A58C"),
        path_arrow('M 825 245 L 825 205 L 125 205 L 125 255', 475, 192, "202 Accepted + job identifier", color="#2F6BFF"),
        '<line x1="350" y1="727" x2="425" y2="727" stroke="#2F6BFF" stroke-width="4"/>',
        text(440, 734, "Synchronous HTTP", size=18),
        '<line x1="650" y1="727" x2="725" y2="727" stroke="#D66A3A" stroke-width="4" stroke-dasharray="10 7"/>',
        text(740, 734, "Asynchronous work", size=18),
        '<line x1="955" y1="727" x2="1030" y2="727" stroke="#28A58C" stroke-width="4"/>',
        text(1045, 734, "Image and result data", size=18),
        text(800, 818, "The client sees a stable service; the API instances, queue, workers and storage remain internal.", size=20, weight=500, anchor="middle", fill="#42566A"),
        '</svg>',
    ]
    OUTPUT.write_text("".join(parts), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
