"""Generate transparent SVG decision trees for the entropy notebook."""
from pathlib import Path
from html import escape

OUT = Path(__file__).resolve().parents[1] / 'picture'

def draw(filename, codes, probabilities, title, two_rows=False):
    symbols = [f'{i:03b}' for i in range(8)]
    leaves = dict(zip(codes, symbols))
    nodes = {c[:i] for c in codes for i in range(len(c)+1)}
    max_depth = max(map(len, codes))
    width, height = 250 * max_depth + 230, 530
    if two_rows:
        width, height = 980, 710
    def descendants(prefix):
        return [i for i,c in enumerate(codes) if c.startswith(prefix)]
    def pos(prefix):
        if two_rows:
            upper = {'': (85, 100), '0': (335, 40), '1': (335, 145),
                     '10': (585, 100), '11': (585, 190), '110': (835, 160)}
            if prefix in upper:
                return upper[prefix]
            ids = descendants(prefix)
            return 85 + 250*(len(prefix)-3), 410 + 60*(sum(ids)/len(ids)-3)
        ids = descendants(prefix)
        return 85 + 250*len(prefix), 40 + 66*sum(ids)/len(ids)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
           f'<title>{escape(title)}</title>',
           '<style>text {font-family:Arial,sans-serif; fill:#172b4d} .label {font-size:19px} .edge {font-size:16px;fill:#49647b}</style>']
    for prefix in sorted(nodes,key=lambda s:(len(s),s)):
        x,y=pos(prefix)
        if prefix in leaves:
            i=symbols.index(leaves[prefix])
            label=f'{leaves[prefix]}   (p = {probabilities[i]})'
            svg.append(f'<text x="{x-48}" y="{y+6}" class="label" font-weight="bold">{label}</text>')
            continue
        yes_ids=descendants(prefix+'0')
        group=[symbols[i] for i in yes_ids]
        label=group[0]+'?' if len(group)==1 else group[0]+'...'+group[-1]+'?'
        svg.append(f'<text x="{x}" y="{y+6}" text-anchor="middle" class="label">{label}</text>')
        for bit,answer in [('0','Yes'),('1','No')]:
            cx,cy=pos(prefix+bit)
            if two_rows and prefix+bit == '111':
                cx,cy = 835,250
            svg.append(f'<path d="M {x+68} {y} L {cx-58} {cy}" stroke="#69849a" stroke-width="2" fill="none"/>')
            svg.append(f'<text x="{(x+68+cx-58)/2}" y="{(y+cy)/2-8}" text-anchor="middle" class="edge">{answer}</text>')
    if two_rows:
        # Matching markers connect the two parts without adding a decision.
        for x,y in [(835,250),(85,480)]:
            svg.append(f'<circle cx="{x}" cy="{y}" r="18" stroke="#49647b" stroke-width="2" fill="none"/>')
            svg.append(f'<text x="{x}" y="{y+6}" text-anchor="middle" class="label">A</text>')
        svg.append('<path d="M 85 498 L 85 512" stroke="#69849a" stroke-width="2" fill="none"/>')
        svg.append('<text x="835" y="290" text-anchor="middle" class="edge">Continue at A below</text>')
    svg.append('</svg>')
    (OUT/filename).write_text('\n'.join(svg)+'\n')

if __name__=='__main__':
    draw('equal-probabilities.svg',[f'{i:03b}' for i in range(8)],['1/8']*8,'Equally likely three-bit source symbols')
    draw('unequal-probabilities.svg',['0','10','110','11100','11101','11110','111110','111111'],['1/2','1/4','1/8']+['1/40']*5,'Unequally likely three-bit source symbols', two_rows=True)
