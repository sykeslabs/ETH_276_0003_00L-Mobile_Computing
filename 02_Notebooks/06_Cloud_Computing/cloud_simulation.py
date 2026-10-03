"""Interactive, progressive cloud-computing simulation used by the notebook."""

from __future__ import annotations

from io import BytesIO

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import ipywidgets as widgets
from IPython.display import display


DEFAULT_REGION_LATENCY_MS = {
    "Zurich": 5,
    "Frankfurt": 15,
    "New York": 90,
    "Singapore": 170,
}

STEP_TITLES = [
    "Baseline: one server",
    "Changing demand",
    "Elasticity",
    "Performance and locality",
    "Content delivery network",
    "Component failure",
    "Regional failure",
    "Cost",
]

TIME = np.arange(60)
CAPACITY_PER_WORKER = 5


def _make_arrivals(normal_rate, burst_rate=None, burst_duration=16):
    """Create repeatable arrivals so slider changes remain comparable."""
    rates = np.full(len(TIME), normal_rate, dtype=float)
    if burst_rate is not None:
        burst_end = min(len(TIME), 18 + burst_duration)
        rates[18:burst_end] = burst_rate
    return np.random.default_rng(12).poisson(rates)


def _run_capacity_queue(arrivals, capacity):
    """Return the outstanding queue for a capacity measured in requests/s."""
    capacity = np.broadcast_to(np.asarray(capacity, dtype=float), len(arrivals))
    queue = np.zeros(len(arrivals), dtype=float)
    completed = np.zeros(len(arrivals), dtype=float)
    waiting = 0.0

    for index, incoming in enumerate(arrivals):
        available = waiting + incoming
        completed[index] = min(available, capacity[index])
        waiting = available - completed[index]
        queue[index] = waiting

    return queue, completed


def _uncompleted_percent(queue, arrivals):
    """Percentage of all requests received so far that remain unfinished."""
    received = np.cumsum(arrivals, dtype=float)
    return 100 * np.asarray(queue, dtype=float) / np.maximum(received, 1)


def _run_fixed_queue(
    arrivals,
    workers,
    capacity_per_worker=CAPACITY_PER_WORKER,
):
    workers = np.asarray(workers, dtype=int)
    queue = np.zeros(len(arrivals), dtype=float)
    completed = np.zeros(len(arrivals), dtype=float)
    waiting = 0.0

    for index, incoming in enumerate(arrivals):
        available = waiting + incoming
        completed[index] = min(
            available,
            workers[index] * capacity_per_worker,
        )
        waiting = available - completed[index]
        queue[index] = waiting

    return queue, completed


def _run_elastic_queue(
    arrivals,
    capacity_per_worker=CAPACITY_PER_WORKER,
    max_workers=4,
    startup_delay=3,
    scale_threshold=8,
):
    workers = np.ones(len(arrivals), dtype=int)
    queue = np.zeros(len(arrivals), dtype=float)
    completed = np.zeros(len(arrivals), dtype=float)
    waiting = 0.0
    pending_start = None
    low_queue_steps = 0

    for index, incoming in enumerate(arrivals):
        if index > 0:
            workers[index] = workers[index - 1]

        if pending_start == index:
            workers[index] = min(max_workers, workers[index] + 1)
            pending_start = None

        available = waiting + incoming
        completed[index] = min(
            available,
            workers[index] * capacity_per_worker,
        )
        waiting = available - completed[index]
        queue[index] = waiting

        if (
            waiting > scale_threshold
            and workers[index] < max_workers
            and pending_start is None
        ):
            pending_start = index + max(1, startup_delay)

        low_queue_steps = low_queue_steps + 1 if waiting < 2 else 0
        if low_queue_steps >= 8 and workers[index] > 1 and pending_start is None:
            workers[index] -= 1
            low_queue_steps = 0

    return queue, completed, workers


def _draw_node(ax, xy, text, introduced, step, width=0.16, height=0.10):
    if introduced > step:
        face, edge, alpha = "#f4f4f4", "#b8b8b8", 0.45
    elif introduced == step:
        face, edge, alpha = "#ffd59a", "#e67817", 1.0
    else:
        face, edge, alpha = "#cfe8ff", "#3178a8", 1.0

    box = FancyBboxPatch(
        (xy[0] - width / 2, xy[1] - height / 2),
        width,
        height,
        boxstyle="round,pad=0.015",
        facecolor=face,
        edgecolor=edge,
        linewidth=2,
        linestyle="--" if introduced > step else "-",
        alpha=alpha,
    )
    ax.add_patch(box)
    ax.text(*xy, text, ha="center", va="center", fontsize=9, alpha=alpha)


def _draw_arrow(ax, start, end, active=True, highlighted=False, label=None):
    color = "#e67817" if highlighted else (
        "#555555" if active else "#c8c8c8"
    )
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "->",
            "color": color,
            "lw": 2,
            "alpha": 1 if active else 0.4,
        },
    )
    if label:
        ax.text(
            (start[0] + end[0]) / 2,
            (start[1] + end[1]) / 2 + 0.045,
            label,
            ha="center",
            fontsize=8,
            color=color,
        )


def _draw_architecture(ax, step):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("System at the current step", fontsize=12, pad=12)

    nodes = {
        "client": ((0.10, 0.66), "Clients", 0),
        "cdn": ((0.28, 0.49), "CDN cache", 4),
        "endpoint": ((0.46, 0.66), "Public endpoint", 0),
        "queue": ((0.64, 0.66), "Queue", 0),
        "worker1": ((0.84, 0.77), "Worker 1", 0),
        "worker2": ((0.84, 0.56), "Worker 2+", 2),
        "region2": ((0.70, 0.25), "Region B", 6),
    }

    for xy, label, introduced in nodes.values():
        _draw_node(ax, xy, label, introduced, step)

    if step >= 4:
        _draw_arrow(ax, (0.18, 0.63), (0.20, 0.53), highlighted=step == 4)
        _draw_arrow(ax, (0.36, 0.53), (0.39, 0.62), highlighted=step == 4)
    else:
        label = "burst" if step == 1 else "latency" if step == 3 else None
        _draw_arrow(
            ax,
            (0.18, 0.66),
            (0.38, 0.66),
            highlighted=step in (1, 3),
            label=label,
        )

    _draw_arrow(ax, (0.54, 0.66), (0.56, 0.66))
    _draw_arrow(ax, (0.72, 0.69), (0.76, 0.75))
    _draw_arrow(
        ax,
        (0.72, 0.63),
        (0.76, 0.58),
        active=step >= 2,
        highlighted=step == 2,
    )
    _draw_arrow(
        ax,
        (0.64, 0.58),
        (0.68, 0.32),
        active=step >= 6,
        highlighted=step == 6,
        label="failover" if step == 6 else None,
    )

    if step == 5:
        ax.plot([0.80, 0.88], [0.52, 0.60], color="#c62828", lw=4)
        ax.plot([0.80, 0.88], [0.60, 0.52], color="#c62828", lw=4)
        ax.text(
            0.84,
            0.45,
            "component failure",
            ha="center",
            color="#c62828",
            fontsize=8,
        )
    if step == 6:
        ax.text(
            0.55,
            0.39,
            "Region A unavailable",
            ha="center",
            color="#c62828",
            fontsize=9,
            weight="bold",
        )
    if step == 7:
        ax.text(
            0.50,
            0.08,
            "Every active resource contributes to cost",
            ha="center",
            color="#e67817",
            fontsize=10,
            weight="bold",
        )


def _plot_metric(ax, step, region_latency_ms, parameters=None):
    parameters = {} if parameters is None else parameters
    ax.grid(alpha=0.22)

    if step == 0:
        demand_rate = parameters.get("demand_rate", 3)
        worker_capacity = parameters.get("worker_capacity", 5)
        arrivals = _make_arrivals(demand_rate)
        queue, _ = _run_fixed_queue(
            arrivals,
            np.ones(len(TIME), dtype=int),
            worker_capacity,
        )
        ax.plot(
            TIME,
            _uncompleted_percent(queue, arrivals),
            color="#c62828",
            lw=2,
        )
        ax.set_title(
            f"Demand {demand_rate} requests/s; "
            f"capacity {worker_capacity} requests/s"
        )

    elif step == 1:
        normal_rate = parameters.get("normal_rate", 3)
        burst_rate = parameters.get("burst_rate", 10)
        worker_capacity = parameters.get("worker_capacity", 5)
        burst_duration = parameters.get("burst_duration", 16)
        arrivals = _make_arrivals(normal_rate, burst_rate, burst_duration)
        queue, _ = _run_fixed_queue(
            arrivals,
            np.ones(len(TIME), dtype=int),
            worker_capacity,
        )
        burst_end = min(len(TIME), 18 + burst_duration)
        ax.plot(
            TIME,
            _uncompleted_percent(queue, arrivals),
            color="#c62828",
            lw=2,
        )
        ax.axvspan(
            18,
            burst_end,
            color="#ffd59a",
            alpha=0.35,
            label="demand burst",
        )
        ax.set_title(
            f"Normal {normal_rate} requests/s; "
            f"burst {burst_rate} requests/s"
        )
        ax.legend()

    elif step == 2:
        burst_rate = parameters.get("burst_rate", 10)
        max_workers = parameters.get("max_workers", 4)
        startup_delay = parameters.get("startup_delay", 3)
        scale_threshold = parameters.get("scale_threshold", 8)
        arrivals = _make_arrivals(3, burst_rate, 16)
        queue, _, workers = _run_elastic_queue(
            arrivals,
            max_workers=max_workers,
            startup_delay=startup_delay,
            scale_threshold=scale_threshold,
        )
        ax.plot(
            TIME,
            _uncompleted_percent(queue, arrivals),
            color="#c62828",
            lw=2,
            label="uncompleted requests",
        )
        second = ax.twinx()
        second.step(
            TIME,
            workers,
            where="post",
            color="#3178a8",
            lw=1.5,
            linestyle="--",
            label="active workers",
        )
        second.set_ylabel("Active workers (workers)", color="#3178a8")
        second.set_ylim(0, max(2, max_workers + 0.5))
        ax.set_title(
            f"Maximum {max_workers} workers; "
            f"startup delay {startup_delay} s"
        )

    elif step == 3:
        demand_rate = parameters.get("demand_rate", 5)
        processing_time_ms = parameters.get("processing_time_ms", 140)
        arrivals = _make_arrivals(demand_rate)
        names = list(region_latency_ms)
        unfinished = []
        for index, latency in enumerate(region_latency_ms.values()):
            measured_latency = parameters.get(f"latency_{index}", latency)
            capacity = 1000 / (processing_time_ms + measured_latency)
            queue, _ = _run_capacity_queue(arrivals, capacity)
            unfinished.append(_uncompleted_percent(queue, arrivals)[-1])
        colours = plt.cm.Reds(np.linspace(0.35, 0.85, len(names)))
        bars = ax.barh(names, unfinished, color=colours)
        ax.bar_label(bars, fmt="%.1f%%")
        ax.set_title(
            f"Demand {demand_rate} requests/s; "
            f"processing {processing_time_ms} ms/request"
        )
        ax.invert_yaxis()
        ax.tick_params(axis="y", labelsize=9, pad=8)
        ax.margins(y=0.12)

    elif step == 4:
        demand_rate = parameters.get("demand_rate", 8)
        origin_latency = parameters.get("origin_latency", 210)
        edge_latency = parameters.get("edge_latency", 22)
        cache_hit_rate = parameters.get("cache_hit_rate", 80) / 100
        arrivals = _make_arrivals(demand_rate)
        miss_latency = origin_latency + edge_latency
        expected_cdn_latency = (
            cache_hit_rate * edge_latency
            + (1 - cache_hit_rate) * miss_latency
        )
        direct_queue, _ = _run_capacity_queue(
            arrivals,
            1000 / origin_latency,
        )
        cdn_queue, _ = _run_capacity_queue(
            arrivals,
            1000 / expected_cdn_latency,
        )
        unfinished = [
            _uncompleted_percent(direct_queue, arrivals)[-1],
            _uncompleted_percent(cdn_queue, arrivals)[-1],
        ]
        bars = ax.bar(
            ["Origin only", "With CDN"],
            unfinished,
            color=["#d66a5e", "#4f9d69"],
        )
        ax.bar_label(bars, fmt="%.1f%%")
        ax.set_title(
            f"Demand {demand_rate} requests/s; "
            f"cache-hit rate {cache_hit_rate:.0%}"
        )

    elif step == 5:
        demand_rate = parameters.get("demand_rate", 8)
        total_workers = parameters.get("total_workers", 2)
        failed_workers = min(
            parameters.get("failed_workers", 1),
            total_workers,
        )
        failure_duration = parameters.get("failure_duration", 17)
        failure_end = min(len(TIME), 25 + failure_duration)
        arrivals = _make_arrivals(demand_rate)
        capacity = np.full(
            len(TIME),
            total_workers * CAPACITY_PER_WORKER,
            dtype=float,
        )
        capacity[25:failure_end] = (
            total_workers - failed_workers
        ) * CAPACITY_PER_WORKER
        queue, _ = _run_capacity_queue(arrivals, capacity)
        ax.plot(
            TIME,
            _uncompleted_percent(queue, arrivals),
            color="#c62828",
            lw=2,
        )
        ax.axvspan(
            25,
            failure_end,
            color="#ef9a9a",
            alpha=0.3,
            label="component failure",
        )
        ax.set_title(
            f"{failed_workers} of {total_workers} workers fail "
            f"for {failure_duration} s"
        )
        ax.legend()

    elif step == 6:
        demand_rate = parameters.get("demand_rate", 4)
        region_capacity = parameters.get("region_capacity", 5)
        backup_capacity = parameters.get("backup_capacity", 5)
        failure_time = parameters.get("failure_time", 25)
        failover_delay = parameters.get("failover_delay", 5)
        recovery_time = min(len(TIME), failure_time + failover_delay)
        arrivals = _make_arrivals(demand_rate)

        single_capacity = np.full(len(TIME), region_capacity, dtype=float)
        single_capacity[failure_time:] = 0
        redundant_capacity = np.full(len(TIME), region_capacity, dtype=float)
        redundant_capacity[failure_time:recovery_time] = 0
        redundant_capacity[recovery_time:] = backup_capacity

        single_queue, _ = _run_capacity_queue(arrivals, single_capacity)
        redundant_queue, _ = _run_capacity_queue(
            arrivals,
            redundant_capacity,
        )
        ax.plot(
            TIME,
            _uncompleted_percent(single_queue, arrivals),
            color="#c62828",
            lw=2,
            label="single region",
        )
        ax.plot(
            TIME,
            _uncompleted_percent(redundant_queue, arrivals),
            color="#4f9d69",
            lw=2,
            label="with failover",
        )
        ax.axvline(
            failure_time,
            color="#555555",
            linestyle="--",
            label="regional failure",
        )
        ax.set_title(
            f"Failover delay {failover_delay} s; "
            f"backup {backup_capacity} requests/s"
        )
        ax.legend(loc="upper left")

    else:
        burst_rate = parameters.get("burst_rate", 10)
        budget_rate = parameters.get("budget_rate", 2.5)
        fixed_rate = parameters.get("fixed_cost_rate", 1.0)
        worker_rate = parameters.get("worker_cost_rate", 0.72)
        region_rate = parameters.get("region_cost_rate", 1.1)
        arrivals = _make_arrivals(3, burst_rate, 16)

        fixed_workers = min(7, int(budget_rate // fixed_rate))
        elastic_limit = min(7, int(budget_rate // worker_rate))
        affordable_regions = min(2, int(budget_rate // region_rate))

        fixed_queue, _ = _run_capacity_queue(
            arrivals,
            fixed_workers * CAPACITY_PER_WORKER,
        )
        if elastic_limit >= 1:
            elastic_queue, _, workers = _run_elastic_queue(
                arrivals,
                max_workers=elastic_limit,
            )
        else:
            elastic_queue, _ = _run_capacity_queue(arrivals, 0)
            workers = np.zeros(len(TIME), dtype=int)
        regional_queue, _ = _run_capacity_queue(
            arrivals,
            affordable_regions * CAPACITY_PER_WORKER,
        )

        ax.plot(
            TIME,
            _uncompleted_percent(fixed_queue, arrivals),
            label=f"fixed pool ({fixed_workers} workers)",
            color="#555555",
        )
        ax.plot(
            TIME,
            _uncompleted_percent(elastic_queue, arrivals),
            label=f"elastic (maximum {elastic_limit} workers)",
            color="#3178a8",
        )
        ax.plot(
            TIME,
            _uncompleted_percent(regional_queue, arrivals),
            label=f"regional deployment ({affordable_regions} regions)",
            color="#e67817",
        )

        fixed_cost = len(TIME) * fixed_workers * fixed_rate
        elastic_cost = np.sum(workers) * worker_rate
        regional_cost = len(TIME) * affordable_regions * region_rate
        cost_text = (
            f"Budget: {budget_rate:.2f} cost units/s\\n"
            "Cost after 60 s (cost units):\\n"
            f"Fixed: {fixed_cost:.1f}  |  "
            f"Elastic: {elastic_cost:.1f}  |  "
            f"Regions: {regional_cost:.1f}"
        )
        ax.text(
            0.02,
            0.97,
            cost_text,
            transform=ax.transAxes,
            va="top",
            fontsize=8,
            bbox={
                "facecolor": "white",
                "alpha": 0.85,
                "edgecolor": "#cccccc",
            },
        )
        ax.set_title(
            f"Burst demand {burst_rate} requests/s under a fixed budget"
        )
        ax.legend(loc="upper right")

    if step == 3:
        # This step uses horizontal bars: cities belong on the categorical
        # y-axis and the shared percentage metric belongs on the x-axis.
        ax.set_xlabel("Uncompleted requests (%)")
        ax.set_xlim(0, 100)
        ax.set_ylabel("")
    else:
        ax.set_ylabel("Uncompleted requests (%)")
        ax.set_ylim(0, 100)
        ax.set_xlabel("" if step == 4 else "Time (s)")

    # Bar charts already display percentages above their bars. For time-series
    # plots, state the final percentage explicitly so it is never hidden at 0%.
    if step not in (3, 4):
        metric_lines = [
            line
            for line in ax.lines
            if len(np.atleast_1d(line.get_ydata())) == len(TIME)
        ]
        if metric_lines:
            summaries = []
            for line in metric_lines:
                label = line.get_label()
                value = float(np.asarray(line.get_ydata())[-1])
                if label.startswith("_") or label == "uncompleted requests":
                    label = "At 60 s"
                summaries.append(f"{label}: {value:.1f}%")
            ax.text(
                0.98,
                0.03,
                "\n".join(summaries),
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=8,
                bbox={
                    "facecolor": "white",
                    "alpha": 0.9,
                    "edgecolor": "#cccccc",
                },
            )


def _render_cloud_simulation_step(step, region_latency_ms, parameters=None):
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(15, 5.3),
        gridspec_kw={"width_ratios": [1, 1.25]},
    )
    _draw_architecture(axes[0], step)
    _plot_metric(axes[1], step, region_latency_ms, parameters)
    fig.suptitle(
        f"Step {step + 1}: {STEP_TITLES[step]}",
        fontsize=15,
        weight="bold",
    )
    fig.tight_layout()
    if step == 3:
        fig.subplots_adjust(wspace=0.42)
    return fig, axes


def _figure_to_png(figure):
    """Render and close a figure so notebook backends cannot display it again."""
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=110, bbox_inches="tight")
    plt.close(figure)
    return buffer.getvalue()


def _new_plot_image():
    """Create the one persistent image surface used by a simulation widget."""
    return widgets.Image(
        format="png",
        layout=widgets.Layout(width="100%", max_width="1200px"),
    )


def _int_slider(description, value, minimum, maximum):
    return widgets.IntSlider(
        description=description,
        value=value,
        min=minimum,
        max=maximum,
        step=1,
        continuous_update=False,
        style={"description_width": "initial"},
        layout=widgets.Layout(width="100%", min_width="0"),
    )


def _float_slider(description, value, minimum, maximum, step=0.1):
    return widgets.FloatSlider(
        description=description,
        value=value,
        min=minimum,
        max=maximum,
        step=step,
        readout_format=".2f",
        continuous_update=False,
        style={"description_width": "initial"},
        layout=widgets.Layout(width="100%", min_width="0"),
    )


def _controls_for_step(step, region_latency_ms):
    if step == 0:
        return {
            "demand_rate": _int_slider("Demand (requests/s)", 3, 1, 10),
            "worker_capacity": _int_slider(
                "Worker capacity (requests/s)",
                5,
                1,
                10,
            ),
        }
    if step == 1:
        return {
            "normal_rate": _int_slider(
                "Normal demand (requests/s)",
                3,
                1,
                8,
            ),
            "burst_rate": _int_slider(
                "Burst demand (requests/s)",
                10,
                3,
                18,
            ),
            "worker_capacity": _int_slider(
                "Worker capacity (requests/s)",
                5,
                1,
                10,
            ),
            "burst_duration": _int_slider(
                "Burst duration (s)",
                16,
                3,
                30,
            ),
        }
    if step == 2:
        return {
            "burst_rate": _int_slider(
                "Burst demand (requests/s)",
                10,
                5,
                18,
            ),
            "max_workers": _int_slider(
                "Maximum workers (workers)",
                4,
                1,
                7,
            ),
            "startup_delay": _int_slider(
                "Worker startup delay (s)",
                3,
                1,
                10,
            ),
            "scale_threshold": _int_slider(
                "Scale-up threshold (requests)",
                8,
                0,
                30,
            ),
        }
    if step == 3:
        controls = {
            "demand_rate": _int_slider(
                "Demand (requests/s)",
                5,
                1,
                12,
            ),
            "processing_time_ms": _int_slider(
                "Processing time (ms/request)",
                140,
                20,
                400,
            ),
        }
        controls.update(
            {
                f"latency_{index}": _int_slider(
                    f"{name} latency (ms)",
                    int(latency),
                    1,
                    max(250, int(latency * 2)),
                )
                for index, (name, latency) in enumerate(
                    region_latency_ms.items()
                )
            }
        )
        return controls
    if step == 4:
        return {
            "demand_rate": _int_slider(
                "Demand (requests/s)",
                8,
                1,
                20,
            ),
            "origin_latency": _int_slider(
                "Origin response time (ms)",
                210,
                10,
                400,
            ),
            "edge_latency": _int_slider(
                "CDN edge response time (ms)",
                22,
                1,
                120,
            ),
            "cache_hit_rate": _int_slider(
                "Cache-hit rate (%)",
                80,
                0,
                100,
            ),
        }
    if step == 5:
        return {
            "demand_rate": _int_slider("Demand (requests/s)", 8, 1, 16),
            "total_workers": _int_slider(
                "Workers before failure (workers)",
                2,
                1,
                6,
            ),
            "failed_workers": _int_slider(
                "Failed workers (workers)",
                1,
                0,
                6,
            ),
            "failure_duration": _int_slider(
                "Failure duration (s)",
                17,
                1,
                30,
            ),
        }
    if step == 6:
        return {
            "demand_rate": _int_slider("Demand (requests/s)", 4, 1, 12),
            "region_capacity": _int_slider(
                "Primary capacity (requests/s)",
                5,
                1,
                15,
            ),
            "backup_capacity": _int_slider(
                "Backup capacity (requests/s)",
                5,
                1,
                15,
            ),
            "failure_time": _int_slider(
                "Regional failure time (s)",
                25,
                5,
                45,
            ),
            "failover_delay": _int_slider(
                "Failover delay (s)",
                5,
                0,
                20,
            ),
        }
    return {
        "burst_rate": _int_slider(
            "Burst demand (requests/s)",
            10,
            5,
            18,
        ),
        "budget_rate": _float_slider(
            "Available budget (cost units/s)",
            2.5,
            0.2,
            6.0,
        ),
        "fixed_cost_rate": _float_slider(
            "Fixed worker cost (cost units/worker/s)",
            1.0,
            0.1,
            3.0,
        ),
        "worker_cost_rate": _float_slider(
            "Elastic worker cost (cost units/worker/s)",
            0.72,
            0.1,
            2.0,
        ),
        "region_cost_rate": _float_slider(
            "Region cost (cost units/region/s)",
            1.1,
            0.2,
            3.0,
        ),
    }


def show_cloud_simulation_step(
    step,
    region_latency_ms=None,
    interactive=True,
):
    """Display one simulation step, optionally with tailored controls."""
    if not isinstance(step, (int, np.integer)) or not 0 <= step < len(STEP_TITLES):
        raise ValueError(
            f"step must be an integer from 0 to {len(STEP_TITLES) - 1}"
        )

    latency_values = dict(
        DEFAULT_REGION_LATENCY_MS
        if region_latency_ms is None
        else region_latency_ms
    )

    if not interactive:
        figure, _ = _render_cloud_simulation_step(step, latency_values)
        plot_image = _new_plot_image()
        plot_image.value = _figure_to_png(figure)
        display(plot_image)
        return None

    controls = _controls_for_step(step, latency_values)

    plot_image = _new_plot_image()
    control_grid = widgets.GridBox(
        list(controls.values()),
        layout=widgets.Layout(
            grid_template_columns=(
                "minmax(0, 1fr)"
                if step == 3
                else "repeat(auto-fit, minmax(320px, 1fr))"
            ),
            grid_gap="6px 16px",
            width="100%",
        ),
    )
    container = widgets.VBox(
        [
            widgets.HTML(
                "<b>Change the parameters and observe the metric:</b>"
            ),
            control_grid,
            plot_image,
        ]
    )

    def refresh(_change=None):
        parameters = {
            name: control.value
            for name, control in controls.items()
        }
        figure, _ = _render_cloud_simulation_step(
            step,
            latency_values,
            parameters,
        )
        plot_image.value = _figure_to_png(figure)

    for control in controls.values():
        control.observe(refresh, names="value")
    refresh()
    display(container)
    return None


def show_progressive_cloud_simulation(region_latency_ms=None):
    """Display all simulation steps as an optional interactive widget."""
    latency_values = dict(
        DEFAULT_REGION_LATENCY_MS
        if region_latency_ms is None
        else region_latency_ms
    )

    step_slider = widgets.IntSlider(
        value=0,
        min=0,
        max=len(STEP_TITLES) - 1,
        step=1,
        description="Step",
        continuous_update=False,
        layout=widgets.Layout(width="82%"),
    )
    play = widgets.Play(
        value=0,
        min=0,
        max=len(STEP_TITLES) - 1,
        step=1,
        interval=1800,
        description="Play",
    )
    widgets.jslink((play, "value"), (step_slider, "value"))
    plot_image = _new_plot_image()

    def render_step(_change=None):
        figure, _ = _render_cloud_simulation_step(
            int(step_slider.value),
            latency_values,
        )
        plot_image.value = _figure_to_png(figure)

    step_slider.observe(render_step, names="value")
    controls = widgets.HBox([play, step_slider])
    render_step()
    display(widgets.VBox([controls, plot_image]))
    return None
