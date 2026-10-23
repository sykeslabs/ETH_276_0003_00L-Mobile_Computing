"""Draw the PID notebook's physical system and measured distances.

Run this file to regenerate the adjacent SVG. Pass --preview PATH to also
produce a PNG for visual checking. The sketch is illustrative, not to scale.
"""

from pathlib import Path
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle


OUTPUT = Path(__file__).with_suffix(".svg")
INK = "#18324A"
GREY = "#7E8D9A"
BLUE = "#2768A7"
GREEN = "#288571"
PURPLE = "#8854A3"
ORANGE = "#C36D28"


def draw_system():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "svg.fonttype": "none",
        "svg.hashsalt": "pid-mass-spring-damper",
        "mathtext.fontset": "dejavusans",
    })
    figure, axis = plt.subplots(figsize=(12, 5.5))
    figure.subplots_adjust(left=0, right=1, bottom=0, top=1)
    axis.set_xlim(0, 1200)
    axis.set_ylim(620, 70)
    axis.set_aspect("equal")
    axis.axis("off")

    def label(x, y, text, *, color=INK, size=17, align="center"):
        axis.text(x, y, text, ha=align, va="center", fontsize=size, color=color)

    def line(xs, ys, *, color=INK, width=2.0, style="-"):
        axis.plot(xs, ys, color=color, linewidth=width, linestyle=style)

    def arrow(x1, y1, x2, y2, *, color=INK, style="-|>", width=2.5):
        axis.add_patch(FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle=style,
            mutation_scale=17, linewidth=width, color=color, shrinkA=0, shrinkB=0,
        ))

    # The spring and dashpot connect the same fixed wall to the same mass.
    wall_x, mass_left, mass_width, centre_x = 105, 650, 170, 735
    zero_x, target_x = 410, 1080
    axis.add_patch(Rectangle(
        (60, 175), 45, 225, facecolor="#EEF1F4", edgecolor=GREY,
        linewidth=1.3, hatch="///",
    ))
    label(95, 145, "Fixed support", size=15)

    spring_y = 240
    spring_start, spring_end = 210, 550
    line([wall_x, spring_start], [spring_y, spring_y])
    spring_xs, spring_ys = [spring_start], [spring_y]
    for index in range(1, 18):
        spring_xs.append(spring_start + index * (spring_end - spring_start) / 18)
        spring_ys.append(spring_y + (17 if index % 2 else -17))
    spring_xs.append(spring_end)
    spring_ys.append(spring_y)
    line(spring_xs, spring_ys, width=2.4)
    line([spring_end, mass_left], [spring_y, spring_y])
    label(370, 194, "Spring", size=17)
    label(370, 288, "$k$ [N/m]", size=16)

    damper_y = 348
    line([wall_x, 335], [damper_y, damper_y])
    # Open cylinder at right, with piston and rod attached to the mass.
    line([480, 335, 335, 480], [318, 318, 378, 378], width=2.4)
    line([440, 440], [323, 373], width=2.4)
    line([440, mass_left], [damper_y, damper_y], width=2.4)
    label(365, 409, "Damper: $c$ [N s/m]", size=16)

    # A rail removes vertical motion; the example controls one position only.
    line([100, 1160], [454, 454], color=GREY, width=2.3)
    line([100, 1160], [466, 466], color=GREY, width=1.0)
    label(160, 444, "Rail", size=14, color=GREY)
    for wheel_x in (mass_left + 35, mass_left + mass_width - 35):
        axis.add_patch(Circle((wheel_x, 442), 12, facecolor="#FFFFFF", edgecolor=GREY, linewidth=2))
    axis.add_patch(FancyBboxPatch(
        (mass_left, 208), mass_width, 222,
        boxstyle="round,pad=0,rounding_size=12",
        facecolor="#E8F1FF", edgecolor=BLUE, linewidth=2.4,
    ))
    label(centre_x, 296, "Mass", size=19)
    label(centre_x, 335, "$m$ [kg]", size=18)

    # Arrows show the positive direction, not a constant force or velocity.
    arrow(centre_x, 142, 938, 142, color=GREEN)
    label(850, 105, r"Velocity $\dot{x}(t)$ [m/s]", color=GREEN, size=16)
    arrow(mass_left + mass_width, 258, 1100, 258, color=BLUE)
    label(970, 218, r"Motor force $u_{\mathrm{act}}(t)$ [N]", color=BLUE, size=16)
    arrow(mass_left + mass_width, 355, 1100, 355, color=ORANGE)
    label(975, 397, "External force $d(t)$ [N]", color=ORANGE, size=15)

    # Zero is the reference position where the spring has zero extension.
    line([zero_x, zero_x], [430, 589], color=GREY, width=1.3, style="--")
    line([centre_x, centre_x], [430, 544], color=GREEN, width=1.3, style="--")
    line([target_x, target_x], [430, 589], color=PURPLE, width=1.3, style="--")
    label(zero_x - 15, 482, "$x=0$", size=15, color=GREY, align="right")
    # Distances are measured from the reference to the mass centre / target.
    arrow(zero_x + 3, 504, centre_x - 3, 504, color=GREEN, style="<->", width=2.0)
    label((zero_x + centre_x) / 2, 529, "$x(t)$ [m]", color=GREEN, size=17)
    arrow(centre_x + 3, 504, target_x - 3, 504, color=PURPLE, style="<->", width=2.0)
    label((centre_x + target_x) / 2, 529, r"$e_{\mathrm{t}}(t)=r(t)-x(t)$ [m]", color=PURPLE, size=16)
    arrow(zero_x + 3, 567, target_x - 3, 567, color=PURPLE, style="<->", width=2.0)
    label((zero_x + target_x) / 2, 598, "Target position $r(t)$ [m]", color=PURPLE, size=17)
    return figure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", type=Path, help="Optional PNG preview path.")
    args = parser.parse_args()
    figure = draw_system()
    figure.savefig(OUTPUT, transparent=True, metadata={"Date": None})
    if args.preview:
        figure.savefig(args.preview, dpi=150, facecolor="white")
    plt.close(figure)
    print(OUTPUT)


if __name__ == "__main__":
    main()
