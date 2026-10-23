"""Generate the secure API request sequence for the cloud notebook."""

from html import escape
from pathlib import Path


WIDTH, HEIGHT = 1500, 945
OUTPUT = Path(__file__).with_suffix(".svg")


COLORS = {
    "dns": "#6F8192",
    "tls": "#2F6BFF",
    "identity": "#6D5BD0",
    "authorization": "#D66A3A",
    "application": "#28A58C",
}


def text(x, y, value, *, size=22, weight=400, anchor="start", fill="#18324A"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(value)}</text>'


def actor(x, label, subtitle):
    return "".join([
        f'<rect x="{x - 105}" y="115" width="210" height="82" rx="20" fill="#FFFFFF" stroke="#9AA9B7" stroke-width="3"/>',
        text(x, 150, label, size=23, weight=500, anchor="middle"),
        text(x, 177, subtitle, size=16, anchor="middle", fill="#5D7083"),
        f'<line x1="{x}" y1="197" x2="{x}" y2="945" stroke="#B8C3CE" stroke-width="2" stroke-dasharray="8 8"/>',
    ])


def arrow(x1, y, x2, label, step, kind, *, return_arrow=False):
    color = COLORS[kind]
    marker = f'arrow-{kind}'
    label_y = y - 13
    number_x = min(x1, x2) - 36
    return "".join([
        f'<circle cx="{number_x}" cy="{y}" r="17" fill="{color}"/>',
        text(number_x, y + 6, str(step), size=16, weight=500, anchor="middle", fill="#FFFFFF"),
        f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="4" marker-end="url(#{marker})"/>',
        text((x1 + x2) / 2, label_y, label, size=18, weight=500, anchor="middle", fill=color),
    ])


def local_step(x, y, w, title, detail, step, kind):
    color = COLORS[kind]
    return "".join([
        f'<circle cx="{x - 28}" cy="{y + 34}" r="17" fill="{color}"/>',
        text(x - 28, y + 40, str(step), size=16, weight=500, anchor="middle", fill="#FFFFFF"),
        f'<rect x="{x}" y="{y}" width="{w}" height="70" rx="17" fill="#FFFFFF" stroke="{color}" stroke-width="3"/>',
        text(x + 18, y + 29, title, size=19, weight=500, fill=color),
        text(x + 18, y + 54, detail, size=16, fill="#5D7083"),
    ])


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    actors = [(170, "Client", "mobile or web app"), (505, "DNS resolver", "locates the service"), (890, "Identity provider", "issues access token"), (1270, "API service", "protects the resource")]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif" width="{WIDTH}" height="{HEIGHT}" viewBox="0 95 {WIDTH} {HEIGHT}" role="img" aria-describedby="desc">',
        '<desc id="desc">A sequence separating DNS, TLS, token authentication, authorization, and the API operation.</desc>',
        '<defs>',
    ]
    for kind, color in COLORS.items():
        parts.append(f'<marker id="arrow-{kind}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="{color}"/></marker>')
    parts.extend([
        '</defs>',
    ])
    for x, label, subtitle in actors:
        parts.append(actor(x, label, subtitle))
    parts.extend([
        arrow(170, 240, 505, "Resolve service name", 1, "dns"),
        arrow(505, 300, 170, "Return IP address", 2, "dns"),
        arrow(170, 380, 1270, "TLS ClientHello and key exchange", 3, "tls"),
        arrow(1270, 445, 170, "Certificate and handshake authentication", 4, "tls"),
        local_step(205, 475, 300, "Validate certificate", "chain, service name and validity", 5, "tls"),
        arrow(170, 600, 890, "Request delegated access", 6, "identity"),
        arrow(890, 660, 170, "Return access token", 7, "identity"),
        arrow(170, 745, 1270, "Encrypted HTTP request + access token", 8, "identity"),
        local_step(930, 780, 300, "Validate token", "signature, issuer, audience and expiry", 9, "identity"),
        local_step(930, 865, 300, "Authorize operation", "is this identity allowed to act?", 10, "authorization"),
        arrow(1270, 970, 170, "Execute operation and return encrypted response", 11, "application"),
        '<rect x="140" y="995" width="1220" height="32" rx="12" fill="#FFFFFF" stroke="#D4DDE6" stroke-width="1"/>',
    ])
    legend = [("DNS", "dns"), ("TLS and PKI", "tls"), ("Token authentication", "identity"), ("Authorization", "authorization"), ("API operation", "application")]
    start_x = 235
    for index, (label, kind) in enumerate(legend):
        x = start_x + index * 245
        parts.append(f'<circle cx="{x}" cy="1011" r="8" fill="{COLORS[kind]}"/>')
        parts.append(text(x + 17, 1017, label, size=16, fill="#42566A"))
    parts.append('</svg>')
    OUTPUT.write_text("".join(parts), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
