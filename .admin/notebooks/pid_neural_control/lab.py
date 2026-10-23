"""Shared simulation and plotting utilities for notebook 04.2.

The notebook keeps the controller definitions and the neural-network training
loop visible.  This module contains the repeated plant simulation, metrics and
plotting code so that the teaching cells can stay focused on the concepts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import matplotlib.pyplot as plt
import numpy as np


DT = 0.05                    # s
DURATION = 20.0              # s
SETPOINT_TIME = 2.0          # s
DEFAULT_SETPOINT = 8.0       # m
MASS = 1.0                   # kg
SPRING_CONSTANT = 1.0        # N/m
DAMPING = 0.2                # N s/m
FORCE_LIMIT = 30.0           # N
INTEGRAL_LIMIT = 50.0        # m s

ERROR_SCALE = 10.0
INTEGRAL_SCALE = 50.0
DERIVATIVE_SCALE = 20.0

TUNED_PID_GAINS = (4.0, 1.0, 3.0)


@dataclass(frozen=True)
class Scenario:
    """Configuration for one closed-loop evaluation."""

    name: str
    setpoint: float = DEFAULT_SETPOINT
    damping: float = DAMPING
    mass: float = MASS
    spring_constant: float = SPRING_CONSTANT
    disturbance_force: float = 0.0
    disturbance_start: float = 8.0
    disturbance_end: float = 8.6
    initial_position: float = 0.0
    initial_velocity: float = 0.0
    cubic_spring_constant: float = 0.0  # N/m³; zero keeps the original plant.
    measurement_delay: float = 0.0     # s; position measurements arrive late.
    actuator_delay: float = 0.0        # s; motor commands take effect late.
    force_limit: float = FORCE_LIMIT   # N; applied identically to PID and NC.
    destabilising_force_coefficient: float = 0.0  # N/m; external force = a*x.
    actuator_polarity: float = 1.0
    polarity_fault_time: float = 8.0   # s; motor direction changes at this time.


SCENARIOS = (
    Scenario("Nominal system"),
    Scenario("Short movement", setpoint=3.0),
    Scenario("Opposite direction", setpoint=-8.0),
    Scenario("Unseen target", setpoint=15.0),
    Scenario("Light load", mass=0.5),
    Scenario("Moderately light load", mass=0.75),
    Scenario("Heavy load", mass=2.0),
    Scenario("Very heavy load", mass=3.0),
    Scenario("Small motor delay", actuator_delay=0.15),
    Scenario("Repeated overcorrection", actuator_delay=0.40),
    Scenario("Long motor delay", actuator_delay=0.80),
    Scenario("Delayed position measurement", measurement_delay=0.60),
    Scenario("Sensor and motor delay", measurement_delay=0.25, actuator_delay=0.25),
    Scenario("Insufficient motor force", force_limit=5.0),
    Scenario("Destabilising external force", destabilising_force_coefficient=2.0),
    Scenario("Reversed motor direction", actuator_polarity=-1.0, polarity_fault_time=8.0),
)


def _setpoint_at(time: float, target: float) -> float:
    return target if time >= SETPOINT_TIME else 0.0


def _disturbance_at(time: float, scenario: Scenario) -> float:
    if scenario.disturbance_start <= time < scenario.disturbance_end:
        return scenario.disturbance_force
    return 0.0


def _external_force_at(time: float, position: float, scenario: Scenario) -> float:
    return (
        _disturbance_at(time, scenario)
        + scenario.destabilising_force_coefficient * position
    )


def _delay_steps(delay: float) -> int:
    steps = int(round(delay / DT))
    if delay < 0.0 or not np.isclose(steps * DT, delay):
        raise ValueError(f"Delay must be a nonnegative multiple of {DT} s.")
    return steps


def _measured_position(position, history, delay_steps):
    if delay_steps == 0 or not history["position"]:
        return position
    # Hold the initial measurement until delayed samples become available.
    return history["position"][max(0, len(history["position"]) - delay_steps)]


def _applied_control(command, time, history, scenario, delay_steps):
    if delay_steps:
        control = (
            history["command"][-delay_steps]
            if len(history["command"]) >= delay_steps else 0.0
        )
    else:
        control = command
    polarity = (
        scenario.actuator_polarity if time >= scenario.polarity_fault_time else 1.0
    )
    return polarity * control


def _plant_acceleration(position, velocity, control, disturbance, scenario):
    """Use the same dynamics for PID and NC, including the optional cubic spring."""

    return (
        -scenario.spring_constant * position
        - scenario.cubic_spring_constant * position**3
        - scenario.damping * velocity
        + control
        + disturbance
    ) / scenario.mass


@lru_cache(maxsize=64)
def _linear_step_coefficients(mass, spring_constant, damping, dt):
    """Exact state transition and constant-force response over one interval."""

    decay = -damping / (2.0 * mass)
    discriminant = decay * decay - spring_constant / mass
    if discriminant > 0.0:
        frequency = np.sqrt(discriminant)
        cosine = np.cosh(frequency * dt)
        sine_over_frequency = np.sinh(frequency * dt) / frequency
    elif discriminant < 0.0:
        frequency = np.sqrt(-discriminant)
        cosine = np.cos(frequency * dt)
        sine_over_frequency = np.sin(frequency * dt) / frequency
    else:
        cosine = 1.0
        sine_over_frequency = dt

    envelope = np.exp(decay * dt)
    p00 = envelope * (cosine - decay * sine_over_frequency)
    p01 = envelope * sine_over_frequency
    p10 = -spring_constant / mass * p01
    p11 = envelope * (cosine + decay * sine_over_frequency)

    if spring_constant != 0.0:
        b0 = (1.0 - p00) / spring_constant
        b1 = p01 / mass
    elif damping != 0.0:
        one_minus_decay = -np.expm1(-damping * dt / mass)
        b0 = dt / damping - mass / damping**2 * one_minus_decay
        b1 = one_minus_decay / damping
    else:
        b0 = dt * dt / (2.0 * mass)
        b1 = dt / mass

    return p00, p01, p10, p11, b0, b1


def advance_plant(position, velocity, applied_force, *, scenario=None, time=0.0, dt=DT):
    """Advance motion while holding the motor force between control updates.

    All 16 notebook examples are linear, so their interval dynamics are solved
    exactly. This also works with PyTorch tensors and preserves their gradients
    during training. The optional cubic spring retains an RK4 fallback.
    """

    scenario = scenario or Scenario("Nominal system")
    constant_force = applied_force + _disturbance_at(time, scenario)
    if scenario.cubic_spring_constant == 0.0:
        effective_spring = (
            scenario.spring_constant - scenario.destabilising_force_coefficient
        )
        p00, p01, p10, p11, b0, b1 = _linear_step_coefficients(
            scenario.mass, effective_spring, scenario.damping, dt,
        )
        return (
            p00 * position + p01 * velocity + b0 * constant_force,
            p10 * position + p11 * velocity + b1 * constant_force,
        )

    # The non-linear extension is not used in the notebook's current examples.
    # Keep its integration separate from the controller's sampling interval.
    def acceleration(stage_position, stage_velocity):
        external_force = (
            _disturbance_at(time, scenario)
            + scenario.destabilising_force_coefficient * stage_position
        )
        return _plant_acceleration(
            stage_position, stage_velocity, applied_force, external_force, scenario,
        )

    substep = dt / 2.0
    for _ in range(2):
        k1x = velocity
        k1v = acceleration(position, velocity)
        k2x = velocity + substep * k1v / 2.0
        k2v = acceleration(position + substep * k1x / 2.0, k2x)
        k3x = velocity + substep * k2v / 2.0
        k3v = acceleration(position + substep * k2x / 2.0, k3x)
        k4x = velocity + substep * k3v
        k4v = acceleration(position + substep * k3x, k4x)
        position = position + substep * (k1x + 2.0 * k2x + 2.0 * k3x + k4x) / 6.0
        velocity = velocity + substep * (k1v + 2.0 * k2v + 2.0 * k3v + k4v) / 6.0
    return position, velocity


def _empty_history() -> dict[str, list[float]]:
    return {
        "time": [],
        "position": [],
        "velocity": [],
        "setpoint": [],
        "error": [],
        "integral": [],
        "derivative": [],
        "measurement": [],
        "command": [],
        "control": [],
        "disturbance": [],
    }


def _finish_history(history: dict[str, list[float]]) -> dict[str, np.ndarray]:
    return {name: np.asarray(values, dtype=float) for name, values in history.items()}


def _record(
    history: dict[str, list[float]],
    *,
    time: float,
    position: float,
    velocity: float,
    setpoint: float,
    error: float,
    integral: float,
    derivative: float,
    measurement: float,
    command: float,
    control: float,
    disturbance: float,
) -> None:
    history["time"].append(time)
    history["position"].append(position)
    history["velocity"].append(velocity)
    history["setpoint"].append(setpoint)
    history["error"].append(error)
    history["integral"].append(integral)
    history["derivative"].append(derivative)
    history["measurement"].append(measurement)
    history["command"].append(command)
    history["control"].append(control)
    history["disturbance"].append(disturbance)


def simulate_pid(
    kp: float,
    ki: float = 0.0,
    kd: float = 0.0,
    *,
    scenario: Scenario | None = None,
    force_limit: float | None = None,
    use_anti_windup: bool = True,
) -> dict[str, np.ndarray]:
    """Simulate a P, PI or PID controller on the common physical plant."""

    scenario = scenario or Scenario("Interactive example")
    force_limit = scenario.force_limit if force_limit is None else force_limit
    measurement_delay_steps = _delay_steps(scenario.measurement_delay)
    actuator_delay_steps = _delay_steps(scenario.actuator_delay)
    steps = int(round(DURATION / DT)) + 1
    position = float(scenario.initial_position)
    velocity = float(scenario.initial_velocity)
    integral = 0.0
    previous_error = _setpoint_at(0.0, scenario.setpoint) - position
    history = _empty_history()

    for step in range(steps):
        time = step * DT
        setpoint = _setpoint_at(time, scenario.setpoint)
        measurement = _measured_position(position, history, measurement_delay_steps)
        error = setpoint - measurement
        candidate_integral = integral + error * DT
        if use_anti_windup:
            candidate_integral = float(
                np.clip(candidate_integral, -INTEGRAL_LIMIT, INTEGRAL_LIMIT)
            )
        derivative = (error - previous_error) / DT
        requested_control = kp * error + ki * candidate_integral + kd * derivative
        command = float(np.clip(requested_control, -force_limit, force_limit))

        # Conditional integration: when the actuator is saturated, do not add
        # error that would push the actuator even farther into saturation.
        drives_further = np.sign(error) == np.sign(requested_control)
        if not (use_anti_windup and requested_control != command and drives_further):
            integral = candidate_integral

        control = _applied_control(command, time, history, scenario, actuator_delay_steps)
        disturbance = _external_force_at(time, position, scenario)
        _record(
            history,
            time=time,
            position=position,
            velocity=velocity,
            setpoint=setpoint,
            error=error,
            integral=integral,
            derivative=derivative,
            measurement=measurement,
            command=command,
            control=control,
            disturbance=disturbance,
        )

        position, velocity = advance_plant(
            position, velocity, control, scenario=scenario, time=time,
        )
        previous_error = error

    return _finish_history(history)


def normalise_observation(error, integral, derivative):
    """Return the three controller inputs on comparable numerical scales."""

    return (
        error / ERROR_SCALE,
        integral / INTEGRAL_SCALE,
        derivative / DERIVATIVE_SCALE,
    )


def simulate_neural_controller(
    model,
    *,
    scenario: Scenario | None = None,
) -> dict[str, np.ndarray]:
    """Run a trained PyTorch controller without tracking gradients."""

    import torch

    scenario = scenario or Scenario("Neural-controller example")
    measurement_delay_steps = _delay_steps(scenario.measurement_delay)
    actuator_delay_steps = _delay_steps(scenario.actuator_delay)
    steps = int(round(DURATION / DT)) + 1
    position = float(scenario.initial_position)
    velocity = float(scenario.initial_velocity)
    integral = 0.0
    previous_error = _setpoint_at(0.0, scenario.setpoint) - position
    history = _empty_history()
    model.eval()

    with torch.no_grad():
        for step in range(steps):
            time = step * DT
            setpoint = _setpoint_at(time, scenario.setpoint)
            measurement = _measured_position(position, history, measurement_delay_steps)
            error = setpoint - measurement
            integral = float(
                np.clip(integral + error * DT, -INTEGRAL_LIMIT, INTEGRAL_LIMIT)
            )
            derivative = (error - previous_error) / DT
            observation = torch.tensor(
                [normalise_observation(error, integral, derivative)],
                dtype=torch.float32,
            )
            command = float(model(observation).item())
            command = float(np.clip(command, -scenario.force_limit, scenario.force_limit))
            control = _applied_control(command, time, history, scenario, actuator_delay_steps)
            disturbance = _external_force_at(time, position, scenario)
            _record(
                history,
                time=time,
                position=position,
                velocity=velocity,
                setpoint=setpoint,
                error=error,
                integral=integral,
                derivative=derivative,
                measurement=measurement,
                command=command,
                control=control,
                disturbance=disturbance,
            )

            position, velocity = advance_plant(
                position, velocity, control, scenario=scenario, time=time,
            )
            previous_error = error

    return _finish_history(history)


def plot_single_response(history: dict[str, np.ndarray]) -> None:
    """Plot one controller response for the P/PI/PID interactive cells."""

    figure, axis = plt.subplots(figsize=(9, 3.8), constrained_layout=True)
    axis.plot(history["time"], history["position"], label="Position $x(t)$")
    axis.plot(history["time"], history["setpoint"], "r--", label="Setpoint $r(t)$")
    axis.set_xlabel("Time [s]")
    axis.set_ylabel("Position [m]")
    axis.grid(True, alpha=0.3)
    axis.legend()
    plt.show()
    plt.close(figure)


def show_p_response(Kp: float = 1.0) -> None:
    plot_single_response(simulate_pid(Kp, 0.0, 0.0))


def show_pi_response(Kp: float = 1.0, Ki: float = 0.0) -> None:
    plot_single_response(simulate_pid(Kp, Ki, 0.0))


def show_pid_response(Kp: float = 1.0, Ki: float = 0.08, Kd: float = 0.0) -> None:
    plot_single_response(simulate_pid(Kp, Ki, Kd))


def plot_training(losses: list[float]) -> None:
    figure, axis = plt.subplots(figsize=(8, 3.4), constrained_layout=True)
    axis.plot(np.arange(1, len(losses) + 1), losses, color="#1f77b4")
    axis.set_xlabel("Training epoch")
    axis.set_ylabel("Trajectory loss")
    axis.grid(True, alpha=0.3)
    plt.show()
    plt.close(figure)


def plot_before_after(untrained, trained, *, scenario: Scenario | None = None) -> None:
    scenario = scenario or Scenario("Nominal system")
    before = simulate_neural_controller(untrained, scenario=scenario)
    after = simulate_neural_controller(trained, scenario=scenario)
    figure, axis = plt.subplots(figsize=(9, 3.8), constrained_layout=True)
    axis.plot(before["time"], before["position"], label="Before training", alpha=0.8)
    axis.plot(after["time"], after["position"], label="After training", linewidth=2)
    axis.plot(after["time"], after["setpoint"], "k--", label="Setpoint")
    axis.set_xlabel("Time [s]")
    axis.set_ylabel("Position [m]")
    axis.grid(True, alpha=0.3)
    axis.legend()
    plt.show()
    plt.close(figure)


def response_metrics(history: dict[str, np.ndarray]) -> dict[str, float | bool]:
    """Calculate metrics after the target step."""

    mask = history["time"] >= SETPOINT_TIME
    time = history["time"][mask]
    position = history["position"][mask]
    setpoint = history["setpoint"][mask]
    control = history["control"][mask]
    error = setpoint - position
    target = float(setpoint[-1])
    amplitude = max(abs(target), 1e-9)

    iae = float(np.sum(np.abs(error)) * DT)
    effort = float(np.sum(control**2) * DT)
    direction = 1.0 if target >= 0.0 else -1.0
    directed_position = direction * position
    overshoot = max(0.0, (float(np.max(directed_position)) - amplitude) / amplitude * 100.0)

    tolerance = max(0.02 * amplitude, 0.05)
    outside = np.flatnonzero(np.abs(error) > tolerance)
    if outside.size == 0:
        settling_time = 0.0
    elif outside[-1] >= len(time) - 1:
        settling_time = float("nan")
    else:
        settling_time = float(time[outside[-1] + 1] - SETPOINT_TIME)

    position_limit = max(5.0 * amplitude + 20.0, 50.0)
    # This finite-run check is not a mathematical stability guarantee.
    bounded_in_simulation = bool(
        np.all(np.isfinite(position))
        and np.all(np.isfinite(control))
        and np.max(np.abs(position)) < position_limit
    )
    return {
        "IAE": iae,
        "Overshoot [%]": overshoot,
        "Settling time [s]": settling_time,
        "Control effort [N²s]": effort,
        "Bounded in simulation": bounded_in_simulation,
    }


def evaluate_controllers(model, scenarios=SCENARIOS):
    """Evaluate tuned PID and a trained neural controller identically."""

    evaluations = []
    for scenario in scenarios:
        pid_history = simulate_pid(*TUNED_PID_GAINS, scenario=scenario)
        neural_history = simulate_neural_controller(model, scenario=scenario)
        evaluations.append(
            {
                "scenario": scenario,
                "PID": pid_history,
                "Neural network": neural_history,
                "PID metrics": response_metrics(pid_history),
                "Neural network metrics": response_metrics(neural_history),
            }
        )
    return evaluations


def plot_comparison(evaluations) -> None:
    """Show numbered PID/NC comparisons; descriptions belong in the notebook."""

    columns = min(4, len(evaluations))
    rows = (len(evaluations) + columns - 1) // columns
    figure, axes = plt.subplots(
        rows, columns, figsize=(12, 2.7 * rows), squeeze=False,
        sharex=True, constrained_layout=True,
    )
    for number, (axis, evaluation) in enumerate(zip(axes.flat, evaluations), start=1):
        pid = evaluation["PID"]
        neural = evaluation["Neural network"]
        axis.plot(
            pid["time"], pid["position"], color="#1f77b4", label="PID", linewidth=1.6,
        )
        axis.plot(
            neural["time"], neural["position"], color="#ff7f0e", label="NC", linewidth=1.6,
        )
        axis.plot(pid["time"], pid["setpoint"], "k--", label="Target")
        scenario = evaluation["scenario"]
        if scenario.actuator_polarity != 1.0:
            axis.axvline(scenario.polarity_fault_time, color="0.5", linestyle=":", linewidth=1)
        axis.text(
            0.035, 0.95, str(number), transform=axis.transAxes,
            ha="left", va="top", fontsize=11, fontweight="bold",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 2},
        )
        axis.set_xlim(0, DURATION)
        axis.set_xticks(np.arange(0, DURATION + 1, 5))
        axis.tick_params(labelsize=9)
        axis.grid(True, alpha=0.3)
        if number > (rows - 1) * columns:
            axis.set_xlabel("Time [s]", fontsize=10)
    for unused_axis in list(axes.flat)[len(evaluations):]:
        unused_axis.set_visible(False)
    figure.supylabel("Position [m]", fontsize=11)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="outside lower center", ncol=3)
    plt.show()
    plt.close(figure)


def metrics_markdown(evaluations) -> str:
    headers = (
        "Example",
        "Controller",
        "IAE [m s]",
        "Overshoot [%]",
        "Settling [s]",
        "Control effort [N²s]",
    )
    rows = []
    for number, evaluation in enumerate(evaluations, start=1):
        for controller in ("PID", "Neural network"):
            metrics = evaluation[f"{controller} metrics"]
            settling = metrics["Settling time [s]"]
            settling_text = "not settled" if np.isnan(settling) else f"{settling:.2f}"
            rows.append(
                (
                    str(number),
                    "PID" if controller == "PID" else "NC",
                    f"{metrics['IAE']:.2f}",
                    f"{metrics['Overshoot [%]']:.2f}",
                    settling_text,
                    f"{metrics['Control effort [N²s]']:.1f}",
                )
            )

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def clone_scenario(scenario: Scenario, **changes) -> Scenario:
    """Convenience helper for optional student experiments."""

    return replace(scenario, **changes)
