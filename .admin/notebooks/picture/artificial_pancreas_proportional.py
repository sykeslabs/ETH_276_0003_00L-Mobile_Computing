"""Generate the static artificial-pancreas figure for notebook 04.1, Section 1.2.1.

Run with Python and NumPy/Matplotlib installed. The PNG is saved beside this file.
This is a simplified teaching model, not a physiological or dosing model.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    # ---------- parameters ----------
    Tsim = 360.0          # total time [min]
    dt   = 0.5
    t    = np.arange(0, Tsim, dt)

    Tg = 200.0             # relaxation of glucose deviation toward baseline [min]
    k_ins = 0.8           # how strongly insulin lowers glucose (positive)
    r = 0.0               # target deviation

    # "glucagon-like" rescue term
    k_gluc = 0.4          # bigger -> stronger recovery from hypoglycemia

    # events
    t_meal1   = 30.0
    meal1_amp = 0.8
    meal1_duration = 60.0  # finite glucose absorption window [min]

    t_sport_start = 120.0
    t_sport_end   = 160.0
    sport_amp     = -1.4   # sport consumes glucose

    t_meal2   = 180.0
    meal2_amp = 0.8
    meal2_duration = 60.0

    # ---------- noise model ----------
    np.random.seed(1)
    noise_std = 0.8     # standard deviation of measurement noise

    # ---------- storage ----------
    x_ol = np.zeros_like(t)    # open loop glucose (true)
    x_cl = np.zeros_like(t)    # closed loop glucose (true)
    u_cl = np.zeros_like(t)    # control signal (insulin)

    # ---------- controller ----------
    u_basal = 0.5
    g_basal = k_ins*u_basal  # background glucose supply balances basal insulin
    Kp = 0.4  # proportional gain; no integral or derivative action

    # ---------- disturbance model ----------
    def meal_absorption(tk, start, duration, amplitude, rapid_onset=False):
        # Finite absorption window; immediate onset for both meals.
        elapsed = tk - start
        if 0.0 <= elapsed <= duration:
            if rapid_onset:
                # Idealized rapid absorption: a step in input, then a smooth fade.
                return amplitude * np.cos(0.5 * np.pi * elapsed / duration)**2
            return amplitude * np.sin(np.pi * elapsed / duration)
        return 0.0

    def exercise_effect(tk):
        # Extra glucose consumption applies only during the sport interval.
        if t_sport_start <= tk < t_sport_end:
            return sport_amp
        return 0.0

    # ---------- simulate ----------
    for k in range(1, len(t)):
        tk = t[k]
        d = (meal_absorption(tk, t_meal1, meal1_duration, meal1_amp, rapid_onset=True)
             + meal_absorption(tk, t_meal2, meal2_duration, meal2_amp, rapid_onset=True)
             + exercise_effect(tk))

        # --- open loop (no feedback, no glucagon) ---
        xdot_ol = -(1.0/Tg)*x_ol[k-1] + g_basal + d - k_ins*u_basal
        x_ol[k] = x_ol[k-1] + dt*xdot_ol

        # --- closed loop (P + glucagon-like) ---
        epsilon_t = np.random.normal(0, noise_std)  # additive sensor noise
        y_meas = x_cl[k-1] + epsilon_t

        e = y_meas - r
        # Insulin lowers glucose, so a positive glucose deviation increases delivery.
        u = u_basal + Kp*e
        u = max(0.0, u)
        u_cl[k] = u

        gluc = k_gluc * max(0.0, -x_cl[k-1])

        xdot_cl = -(1.0/Tg)*x_cl[k-1] + g_basal + d - k_ins*u + gluc
        x_cl[k] = x_cl[k-1] + dt*xdot_cl

    # ---------- plot ----------
    plt.rcParams.update({"font.size": 12, "axes.titlesize": 17, "axes.labelsize": 13})
    fig, ax = plt.subplots(figsize=(12, 5.8))
    ax.plot(t, x_ol, color="#2563eb", linewidth=2.3, label="Open-loop: basal insulin only")
    ax.plot(t, x_cl, color="#d97706", linewidth=2.0, label="Closed-loop: P + glucagon-like rescue")
    ax.axhline(0.0, color="#475569", linestyle="--", linewidth=1.3, label="Target")
    ax.axvspan(t_sport_start, t_sport_end, color="#8b5cf6", alpha=0.13, label="Sport (120-160 min)")
    for start, label in [(t_meal1, "Meal 1"), (t_meal2, "Meal 2")]:
        ax.axvline(start, color="#64748b", linestyle=":", linewidth=1.4)
        ax.text(start + 3, 0.94, label, transform=ax.get_xaxis_transform(),
                va="top", color="#475569", fontsize=11)
    ax.set(xlabel="Time [min]", ylabel="Glucose deviation [arbitrary units]",
           xlim=(0, Tsim))
    ax.grid(axis="y", alpha=0.18)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="lower right", frameon=True, facecolor="white",
              framealpha=0.95, fontsize=11)
    fig.tight_layout()
    output = Path(__file__).with_suffix(".png")
    fig.savefig(output, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
