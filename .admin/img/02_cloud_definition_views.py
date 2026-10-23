"""Generate the cloud-definition comparison used in the cloud notebook."""

from html import escape
from pathlib import Path


WIDTH, HEIGHT = 1400, 760
OUTPUT = Path(__file__).with_suffix(".svg")


def multiline(x, y, lines, *, size=24, weight=400, anchor="start", fill="#18324A", gap=30):
    spans = []
    for index, line in enumerate(lines):
        dy = 0 if index == 0 else gap
        spans.append(f'<tspan x="{x}" dy="{dy}">{escape(line)}</tspan>')
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}">' + "".join(spans) + "</text>"
    )


def box(x, y, w, h, title, lines, color):
    return "".join(
        [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" fill="#FFFFFF" '
            f'stroke="{color}" stroke-width="3"/>',
            multiline(x + 24, y + 43, [title], size=24, weight=500),
            multiline(x + 24, y + 77, lines, size=19, fill="#42566A", gap=25),
        ]
    )


def connector(x1, y1, x2, y2):
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        'stroke="#9AA9B7" stroke-width="3" marker-end="url(#arrow)"/>'
    )


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-describedby="desc">',
        '<desc id="desc">Five sources emphasize different aspects of cloud computing while sharing a common core.</desc>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" '
        'markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#9AA9B7"/></marker></defs>',
        connector(335, 162, 470, 245),
        connector(700, 150, 700, 180),
        connector(1065, 162, 930, 245),
        connector(430, 610, 500, 540),
        connector(970, 610, 900, 540),
        '<rect x="445" y="180" width="510" height="380" rx="30" fill="#EAF1FF" stroke="#2F6BFF" stroke-width="4"/>',
        multiline(700, 230, ["Shared core"], size=30, weight=500, anchor="middle", fill="#173B7A"),
        multiline(500, 285, [
            "Network-accessible services",
            "On-demand provisioning",
            "Shared or pooled resources",
            "Scalability and elasticity",
            "Measurement and provider relationship",
        ], size=23, fill="#18324A", gap=48),
        box(55, 32, 330, 130, "NIST [1]", ["Structured taxonomy", "Characteristics and models"], "#2F6BFF"),
        box(535, 20, 330, 130, "ISO [2]", ["Common vocabulary", "Consistent terminology"], "#6D5BD0"),
        box(1015, 32, 330, 130, "Berkeley [3]", ["Elasticity and economics", "Pay-per-use services"], "#28A58C"),
        box(110, 610, 360, 130, "Vaquero et al. [4]", ["Consensus definition", "Virtualized and scalable"], "#D66A3A"),
        box(930, 610, 360, 130, "Buyya et al. [5]", ["Computing as a utility", "SLA and quality of service"], "#B14D8D"),
        '</svg>',
    ]
    OUTPUT.write_text("".join(parts), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
