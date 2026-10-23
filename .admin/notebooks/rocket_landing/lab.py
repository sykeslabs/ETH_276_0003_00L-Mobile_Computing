"""Implementation for notebook 04.3, PID for Rocket Landing.

The notebook runs this file with IPython's ``%run -i`` so rerunning its
launch cell also disconnects and closes the previous cockpit widgets.
The replay and cockpit appearance are stored in adjacent HTML/CSS files.
"""

# Physical constants
import numpy as np
import matplotlib.pyplot as plt

GRAVITY = 9.81            # m/s²
MASS = 1.0                # kg; a teaching model, not the mass of a real booster
MAX_THRUST = 20.0         # N
DELTA_TIME = 0.11         # s
MAX_TIME = 500.0          # s
INITIAL_POSITION = [0.0, 100.0]  # x, y in m
INITIAL_VELOCITY = [0.0, 0.0]    # vx, vy in m/s
PAD_HALF_WIDTH = 2.0      # m from the pad center
MAX_LANDING_SPEED = 0.5   # m/s, for each velocity component

# PID controllers and flight simulation
class PIDController:
    def __init__(self, kp, ki, kd):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.previous_error = 0.0
        self.integral = 0.0

    def update(self, error, dt):
        self.integral += error * dt
        derivative = (error - self.previous_error) / dt
        output = self.kp * error + self.ki * self.integral + self.kd * derivative
        self.previous_error = error
        return output


class Rocket:
    def __init__(self, position, velocity):
        self.position = np.array(position, dtype=float)
        self.velocity = np.array(velocity, dtype=float)
        self.mass = MASS
        self.thrust = 0.0
        self.thrust_angle = 0.0

    def acceleration(self):
        # Angle is measured from vertical. Positive angles push to the right.
        ax = self.thrust * np.sin(self.thrust_angle) / self.mass
        ay = self.thrust * np.cos(self.thrust_angle) / self.mass - GRAVITY
        return np.array([ax, ay])

    def update(self, acceleration, dt):
        self.velocity += acceleration * dt
        self.position += self.velocity * dt


def target_descent_speed(height):
    return -0.2 - 0.1 * max(float(height), 0.0)


def landing_outcome(position, velocity, touched_ground):
    if not touched_ground:
        return "Timeout: the rocket did not reach the ground."
    problems = []
    if abs(position[0]) > PAD_HALF_WIDTH:
        problems.append("missed the pad")
    if abs(velocity[1]) > MAX_LANDING_SPEED:
        problems.append("vertical speed too high")
    if abs(velocity[0]) > MAX_LANDING_SPEED:
        problems.append("sideways speed too high")
    if problems:
        return "Landing failed: " + "; ".join(problems) + "."
    return "Successful landing! Gentle touchdown on the pad."


def simulate_landing(velocity_gains, horizontal_gains, wind_std=1.0, seed=7):
    # Reset both the controller memory and the wind sequence for every run.
    rocket = Rocket(INITIAL_POSITION, INITIAL_VELOCITY)
    velocity_pid = PIDController(*velocity_gains)
    horizontal_pid = PIDController(*horizontal_gains)
    rng = np.random.default_rng(seed)

    history = {"time": [0.0], "position": [rocket.position.copy()],
               "velocity": [rocket.velocity.copy()],
               "target_velocity": [target_descent_speed(rocket.position[1])],
               "thrust": [0.0], "requested_thrust": [0.0], "angle": [0.0],
               "wind_acceleration": [0.0]}
    time = 0.0
    touched_ground = False

    while time < MAX_TIME:
        dt = min(DELTA_TIME, MAX_TIME - time)
        target_velocity = target_descent_speed(rocket.position[1])
        velocity_error = target_velocity - rocket.velocity[1]
        horizontal_error = -rocket.position[0]
        requested_thrust = velocity_pid.update(velocity_error, dt)
        direction = horizontal_pid.update(horizontal_error, dt)
        rocket.thrust = float(np.clip(requested_thrust, 0.0, MAX_THRUST))
        rocket.thrust_angle = float(np.arctan2(direction, 1.0))

        # This is acceleration (m/s²), not force (N).
        wind_acceleration = rng.normal(0.0, wind_std)
        acceleration = rocket.acceleration() + np.array([wind_acceleration, 0.0])
        previous_position = rocket.position.copy()
        previous_velocity = rocket.velocity.copy()
        rocket.update(acceleration, dt)

        if rocket.position[1] <= 0.0:
            # Approximate contact by interpolating the last simulation step.
            fraction = previous_position[1] / (previous_position[1] - rocket.position[1])
            rocket.position = previous_position + fraction * (rocket.position - previous_position)
            rocket.velocity = previous_velocity + fraction * (rocket.velocity - previous_velocity)
            rocket.position[1] = 0.0
            time += fraction * dt
            touched_ground = True
        else:
            time += dt

        history["time"].append(time)
        history["position"].append(rocket.position.copy())
        history["velocity"].append(rocket.velocity.copy())
        history["target_velocity"].append(target_descent_speed(rocket.position[1]))
        history["thrust"].append(rocket.thrust)
        history["requested_thrust"].append(requested_thrust)
        history["angle"].append(rocket.thrust_angle)
        history["wind_acceleration"].append(wind_acceleration)
        if touched_ground:
            break

    result = {key: np.asarray(values) for key, values in history.items()}
    result["touched_ground"] = touched_ground
    result["outcome"] = landing_outcome(rocket.position, rocket.velocity, touched_ground)
    return result

# Flight diagnostics
def plot_landing(result):
    time = result["time"]
    positions = result["position"]
    velocities = result["velocity"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)

    ax = axes[0, 0]
    ax.plot(positions[:, 0], positions[:, 1], color="tab:blue", label="Flight path")
    ax.scatter(*positions[0], marker="o", label="Start", zorder=3)
    ax.scatter(*positions[-1], marker="X", s=85, color="tab:red", label="Final position", zorder=4)
    ax.plot([-PAD_HALF_WIDTH, PAD_HALF_WIDTH], [0, 0], color="tab:green", linewidth=7,
            label="Target landing pad", solid_capstyle="butt")
    ax.axhline(0, color="0.4", linewidth=1)
    ax.set(xlabel="Horizontal position (m)", ylabel="Height (m)", title="Where did the rocket go?")
    ax.legend(loc="best")

    ax = axes[0, 1]
    ax.plot(time, result["target_velocity"], "--", color="0.3", label="Target vertical speed")
    ax.plot(time, velocities[:, 1], label="Vertical velocity")
    ax.plot(time, velocities[:, 0], label="Horizontal velocity")
    ax.axhspan(-MAX_LANDING_SPEED, MAX_LANDING_SPEED, color="tab:green", alpha=0.15,
               label="Allowed speeds at touchdown")
    ax.set(xlabel="Time (s)", ylabel="Velocity (m/s)", title="Did it slow down in time?")
    ax.legend(loc="best")

    ax = axes[1, 0]
    ax.plot(time, result["requested_thrust"], "--", color="0.5", label="PID request")
    ax.plot(time, result["thrust"], color="tab:orange", label="Applied thrust")
    ax.axhline(MAX_THRUST, color="tab:red", linestyle=":", label="Engine limit")
    ax.axhline(MASS * GRAVITY, color="0.3", linestyle=":", label="Weight (upright hover)")
    ax.set(xlabel="Time (s)", ylabel="Thrust (N)", title="What did the engine do?")
    ax.legend(loc="best")

    ax = axes[1, 1]
    ax.plot(time, np.rad2deg(result["angle"]), color="tab:purple")
    ax.axhline(0, color="0.5", linewidth=1)
    ax.set(xlabel="Time (s)", ylabel="Thrust angle from vertical (degrees)",
           title="How strongly did it steer?")

    for ax in axes.flat:
        ax.grid(alpha=0.25)
    fig.suptitle(result["outcome"], fontsize=13)
    # Return a closed figure so the inline backend cannot display it a second time.
    plt.close(fig)
    return fig

# Replay data and offline audio
import base64
import json
from pathlib import Path
from html import escape
from IPython.display import HTML, display


# Resolve assets from this helper, independently of the notebook's working directory.
HELPER_DIR = Path(__file__).resolve().parent
REPLAY_TEMPLATE = (HELPER_DIR / "replay.html").read_text(encoding="utf-8")
_applause_file = HELPER_DIR.parent / "sounds/rocket_landing_applause.wav"
APPLAUSE_WAV_BASE64 = (
    base64.b64encode(_applause_file.read_bytes()).decode("ascii") if _applause_file.is_file() else ""
)
if not APPLAUSE_WAV_BASE64:
    print("Applause WAV is missing; successful landings will play the happy chime only.")


def landing_flight_data(flight, autoplay=True, include_sound=True):
    """Prepare one attempt; subsequent updates reuse the player's audio recording."""
    # Keep long timeouts compact; always retain the exact final contact state.
    count = len(flight["time"])
    stride = max(1, int(np.ceil(count / 900)))
    indices = np.unique(np.r_[np.arange(0, count, stride), count - 1])
    # A flag has inertia: show a 0.35 s smoothed response to the actual gusts.
    # The wind itself, and its effect on the rocket, remain unchanged.
    flag_wind = np.zeros(count)
    for i in range(1, count):
        dt = flight["time"][i] - flight["time"][i - 1]
        weight = -np.expm1(-dt / 0.35)
        flag_wind[i] = flag_wind[i - 1] + weight * (flight["wind_acceleration"][i] - flag_wind[i - 1])
    frames = np.column_stack([
        flight["time"], flight["position"], flight["velocity"],
        flight["thrust"], flight["angle"], flag_wind,
    ])[indices].round(6).tolist()
    payload = {
        "frames": frames,
        "outcome": flight["outcome"],
        "contact": bool(flight["touched_ground"]),
        "success": flight["outcome"].startswith("Successful"),
        "xmax": max(8.0, float(np.max(np.abs(flight["position"][:, 0]))) * 1.15),
        "ymax": max(110.0, float(np.max(flight["position"][:, 1])) * 1.12),
        "pad": PAD_HALF_WIDTH, "maxThrust": MAX_THRUST, "autoplay": bool(autoplay),
    }
    if include_sound:
        payload["applauseWav"] = APPLAUSE_WAV_BASE64
    return payload


def landing_replay_html(flight, autoplay=True, channel=""):
    """Create the player once; keep its unlocked audio context across attempts."""
    payload = json.dumps(landing_flight_data(flight, autoplay),
                         separators=(",", ":"), allow_nan=False)
    document = REPLAY_TEMPLATE
    document = document.replace("__FLIGHT_DATA__", payload)
    document = document.replace("__REPLAY_CHANNEL__", json.dumps(channel))
    # Listen in the notebook document while the player stays sandboxed.
    fit_height = """
const frame = this;
if (frame._rocketResizeHandler) window.removeEventListener('message', frame._rocketResizeHandler);
frame._rocketResizeHandler = event => {
 if (!frame.isConnected) {
  window.removeEventListener('message', frame._rocketResizeHandler); return;
 }
 if (event.source === frame.contentWindow && event.data?.type === 'rocket-replay-size' &&
     Number.isFinite(event.data.height)) {
  frame.style.height = `${Math.max(1, Math.ceil(event.data.height))}px`;
 }
};
window.addEventListener('message', frame._rocketResizeHandler);
frame.contentWindow.postMessage({type: 'rocket-replay-measure'}, '*');
"""
    # Keep this iframe alive while updating the flight data through a sibling iframe.
    return ('<iframe title="Rocket landing replay" sandbox="allow-scripts" allow="autoplay" '
            'style="width:100%;max-width:960px;height:660px;border:0;display:block;" '
            'onload="' + escape(fit_height, quote=True) + '" '
            'srcdoc="' + escape(document, quote=True) + '"></iframe>')


def landing_replay_update_html(flight, channel, revision, autoplay=True):
    """Deliver new data without replacing the replay or resetting sound permission."""
    packet = json.dumps({
        "type": "rocket-flight-update", "channel": channel, "revision": revision,
        "flight": landing_flight_data(flight, autoplay, include_sound=False),
    }, separators=(",", ":"), allow_nan=False)
    document = r'''<!doctype html><html><body><script>
const packet = __UPDATE_DATA__;
let attempts = 0;
// The two sandboxed iframes share a parent in the lab widget.
// Retry until acknowledged so widget rendering order does not lose an update.
function send() {
 for (let i = 0; i < window.parent.frames.length; i++) {
  const target = window.parent.frames[i];
  if (target !== window) target.postMessage(packet, '*');
 }
 if (++attempts >= 200) clearInterval(timer);
}
const timer = setInterval(send, 100);
window.addEventListener('message', event => {
 const message = event.data;
 if (message?.type === 'rocket-flight-ack' && message.channel === packet.channel &&
     message.revision === packet.revision) clearInterval(timer);
});
window.addEventListener('pagehide', () => clearInterval(timer));
send();
</script></body></html>'''.replace("__UPDATE_DATA__", packet)
    return ('<iframe title="Landing attempt data" sandbox="allow-scripts" '
            'aria-hidden="true" tabindex="-1" style="display:none" '
            'srcdoc="' + escape(document, quote=True) + '"></iframe>')

# Cockpit widgets and launch controls
from io import BytesIO
from uuid import uuid4

try:
    import ipywidgets as widgets
except ImportError:
    widgets = None

# Disconnect the previous lab when this cell is rerun.
if "landing_controls" in globals() and "update_landing" in globals():
    for previous_control in landing_controls.values():
        previous_control.unobserve(update_landing, names="value")
if "landing_panel" in globals():
    def close_landing_panel(panel):
        for child in getattr(panel, "children", ()):
            close_landing_panel(child)
        panel.close()
    close_landing_panel(landing_panel)
if "play_attempt_button" in globals() and "play_new_attempt" in globals():
    play_attempt_button.on_click(play_new_attempt, remove=True)

# These remain the deliberately untuned starting settings.
VELOCITY_GAINS = (0.1, 0.1, 0.1)
HORIZONTAL_GAINS = (0.1, 0.1, 0.1)
WIND_STD = 1.0
SEED = 7

if widgets is None:
    print("Gain sliders need ipywidgets from the course environment. "
          "For now, edit the settings above and rerun this cell.")
    result = simulate_landing(VELOCITY_GAINS, HORIZONTAL_GAINS, WIND_STD, SEED)
    display(HTML(landing_replay_html(result)))
    display(plot_landing(result))
else:
    def gain_slider(label, value, maximum, step):
        return widgets.FloatSlider(
            description=label, value=value, min=0.0, max=maximum, step=step,
            readout_format=".2f", continuous_update=False,
            style={"description_width": "32px"}, layout=widgets.Layout(width="100%", min_width="0px"),
        )

    landing_controls = {
        "v_kp": gain_slider("Kp", VELOCITY_GAINS[0], 12.0, 0.05),
        "v_ki": gain_slider("Ki", VELOCITY_GAINS[1], 4.0, 0.05),
        "v_kd": gain_slider("Kd", VELOCITY_GAINS[2], 2.0, 0.05),
        "h_kp": gain_slider("Kp", HORIZONTAL_GAINS[0], 1.0, 0.01),
        "h_ki": gain_slider("Ki", HORIZONTAL_GAINS[1], 0.5, 0.01),
        "h_kd": gain_slider("Kd", HORIZONTAL_GAINS[2], 2.0, 0.01),
        "wind": widgets.FloatSlider(description="Horizontal Wind", min=0.0, max=5.0,
            step=0.1, value=WIND_STD, continuous_update=False, readout_format=".1f",
            style={"description_width": "115px"}, layout=widgets.Layout(width="340px")),
        "seed": widgets.BoundedIntText(description="Seed", min=0, max=2147483647, value=SEED,
            style={"description_width": "40px"}, layout=widgets.Layout(width="145px")),
        "seed_mode": widgets.RadioButtons(
            options=[("Increment seed each play", "auto"), ("Keep seed fixed", "fixed")],
            value="auto", layout=widgets.Layout(width="220px")),
        "autoplay": widgets.Checkbox(value=True, description="Play after changes",
            indent=False, layout=widgets.Layout(width="180px")),
    }
    replay_channel = uuid4().hex
    replay_revision = 0
    replay_view = widgets.HTML(layout=widgets.Layout(width="100%"))
    replay_data_view = widgets.HTML(layout=widgets.Layout(display="none"))
    diagnostic_view = widgets.Image(format="png", layout=widgets.Layout(width="100%"))
    diagnostic_panel = widgets.Accordion(children=[diagnostic_view], selected_index=None)
    diagnostic_panel.set_title(0, "Flight diagnostics: trajectory, velocity, thrust, steering")
    play_attempt_button = widgets.Button(description="Play new attempt",
        button_style="success", layout=widgets.Layout(width="200px", height="42px"))

    def update_landing(change=None, *, play=False):
        # A replay keeps the same flight. A new played attempt can advance its seed.
        global result, replay_revision
        if change and change["owner"] is landing_controls["seed_mode"]:
            return
        autoplay = play or landing_controls["autoplay"].value
        seed_control = landing_controls["seed"]
        editing_seed = change and change["owner"] is seed_control
        if replay_view.value and autoplay and not editing_seed and landing_controls["seed_mode"].value == "auto":
            # Avoid recursive observers and a duplicate simulation while incrementing.
            seed_control.unobserve(update_landing, names="value")
            try:
                seed_control.value = (seed_control.value + 1) % (seed_control.max + 1)
            finally:
                seed_control.observe(update_landing, names="value")
        vertical = tuple(landing_controls[key].value for key in ("v_kp", "v_ki", "v_kd"))
        horizontal = tuple(landing_controls[key].value for key in ("h_kp", "h_ki", "h_kd"))
        wind, seed = landing_controls["wind"].value, landing_controls["seed"].value
        result = simulate_landing(vertical, horizontal, wind, seed)
        if not replay_view.value:
            replay_view.value = landing_replay_html(
                result, autoplay, replay_channel)
        else:
            replay_revision += 1
            replay_data_view.value = landing_replay_update_html(
                result, replay_channel, replay_revision, autoplay)
        # Replace one image inside the accordion; do not emit a second cell output.
        figure = plot_landing(result)
        image_bytes = BytesIO()
        figure.savefig(image_bytes, format="png", dpi=100, bbox_inches="tight")
        diagnostic_view.value = image_bytes.getvalue()

    def play_new_attempt(_button):
        update_landing(play=True)

    play_attempt_button.on_click(play_new_attempt)
    for control in landing_controls.values():
        control.observe(update_landing, names="value")

    cockpit_style = "<style>" + (HELPER_DIR / "cockpit.css").read_text(encoding="utf-8") + "</style>"
    cockpit_heading = widgets.HTML(cockpit_style +
        '<div class="rocket-deck-heading"><div>'
        '<strong>Flight deck</strong></div><span class="rocket-deck-tag">PID CONTROL</span></div>')
    vertical_panel = widgets.VBox([
        widgets.HTML('<div class="rocket-panel-heading"><span class="rocket-panel-number">01</span>DESCENT CONTROL</div>')
    ] + [landing_controls[key] for key in ("v_kp", "v_ki", "v_kd")],
        layout=widgets.Layout(flex="1 1 280px", min_width="0px"))
    vertical_panel.add_class("rocket-pid-panel")
    horizontal_panel = widgets.VBox([
        widgets.HTML('<div class="rocket-panel-heading"><span class="rocket-panel-number">02</span>STEERING CONTROL</div>')
    ] + [landing_controls[key] for key in ("h_kp", "h_ki", "h_kd")],
        layout=widgets.Layout(flex="1 1 280px", min_width="0px"))
    horizontal_panel.add_class("rocket-pid-panel").add_class("rocket-steering")
    environment_panel = widgets.VBox([
        widgets.HTML('<div class="rocket-section-caption">ENVIRONMENT &amp; SEED</div>'),
        widgets.Box([landing_controls[key] for key in ("wind", "seed", "seed_mode")],
            layout=widgets.Layout(display="flex", flex_flow="row wrap", align_items="center", gap="12px")),
    ])
    environment_panel.add_class("rocket-environment")
    launch_row = widgets.Box([play_attempt_button, landing_controls["autoplay"]],
        layout=widgets.Layout(display="flex", flex_flow="row wrap", align_items="center", gap="18px"))
    launch_row.add_class("rocket-launch-row")
    cockpit_panel = widgets.VBox([
        cockpit_heading,
        widgets.Box([vertical_panel, horizontal_panel],
            layout=widgets.Layout(display="flex", flex_flow="row wrap", gap="12px")).add_class("rocket-pid-row"),
        environment_panel, launch_row,
    ], layout=widgets.Layout(width="100%", max_width="960px"))
    cockpit_panel.add_class("rocket-cockpit")
    landing_panel = widgets.VBox([
        cockpit_panel, replay_view, replay_data_view, diagnostic_panel,
    ], layout=widgets.Layout(width="100%", max_width="960px"))
    display(landing_panel)
    update_landing()
