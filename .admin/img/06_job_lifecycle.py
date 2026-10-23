"""Generate the asynchronous image-processing job lifecycle."""

from html import escape
from pathlib import Path


WIDTH, HEIGHT = 1400, 540
OUTPUT = Path(__file__).with_suffix(".svg")


def text(x, y, value, *, size=22, weight=400, anchor="start", fill="#18324A"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(value)}</text>'


def node(x, y, w, h, title, subtitle, *, fill="#E8F1FF", stroke="#4B78C2"):
    return "".join([
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" fill="{fill}" stroke="{stroke}" stroke-width="3"/>',
        text(x + w / 2, y + 40, title, size=24, weight=500, anchor="middle"),
        text(x + w / 2, y + 70, subtitle, size=17, anchor="middle", fill="#5D7083"),
    ])


def arrow(x1, y1, x2, y2, label="", *, color="#2F6BFF", dash="", label_y=-12):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    result = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="4" marker-end="url(#arrow-{color[1:]})"{dash_attr}/>']
    if label:
        result.append(text((x1 + x2) / 2, (y1 + y2) / 2 + label_y, label, size=17, weight=500, anchor="middle", fill=color))
    return "".join(result)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif" width="{WIDTH}" height="{HEIGHT}" viewBox="0 100 {WIDTH} {HEIGHT}" role="img" aria-describedby="desc">',
        '<desc id="desc">The API accepts a job and returns an identifier before a worker completes or fails the job.</desc>',
        '<defs>',
        '<marker id="arrow-2F6BFF" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#2F6BFF"/></marker>',
        '<marker id="arrow-D66A3A" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#D66A3A"/></marker>',
        '</defs>',
        node(90, 120, 210, 90, "Client", "submits an image", fill="#FFF0DE", stroke="#E49A3A"),
        node(455, 120, 250, 90, "API", "creates a job identifier"),
        arrow(300, 150, 445, 150, "POST /images", label_y=-16),
        arrow(455, 195, 310, 195, "202 Accepted + job ID", label_y=28),
        '<rect x="90" y="255" width="615" height="62" rx="16" fill="#FFFFFF" stroke="#9AA9B7" stroke-width="2" stroke-dasharray="8 6"/>',
        text(397, 282, "GET /jobs/{id}", size=19, weight=500, anchor="middle", fill="#42566A"),
        text(397, 305, "pending / processing / completed / failed", size=17, anchor="middle", fill="#5D7083"),
        '<path d="M 580 220 L 580 355 L 215 355 L 215 390" fill="none" stroke="#2F6BFF" stroke-width="4" marker-end="url(#arrow-2F6BFF)"/>',
        node(80, 400, 235, 100, "Accepted", "job ID created"),
        node(400, 400, 235, 100, "Queued", "waiting for a worker", fill="#FFF0DE", stroke="#D66A3A"),
        node(720, 400, 235, 100, "Processing", "worker owns the job", fill="#FFF0DE", stroke="#D66A3A"),
        node(1045, 355, 250, 100, "Completed", "result location stored", fill="#E8F7F3", stroke="#28A58C"),
        node(1045, 520, 250, 100, "Failed", "error recorded or retried", fill="#FCE8E6", stroke="#D65745"),
        arrow(315, 450, 390, 450),
        arrow(635, 450, 710, 450),
        arrow(955, 435, 1035, 405, "success", color="#2F6BFF", label_y=-18),
        arrow(955, 475, 1035, 555, "error", color="#D66A3A", label_y=18),
        '<rect x="80" y="560" width="875" height="62" rx="15" fill="#EAF1FF" stroke="#A9C2F5" stroke-width="2"/>',
        text(517, 599, "202 Accepted confirms that the job was accepted - it does not confirm successful processing.", size=20, weight=500, anchor="middle", fill="#244D9B"),
        '</svg>',
    ]
    OUTPUT.write_text("".join(parts), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
