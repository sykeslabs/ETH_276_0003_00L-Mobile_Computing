"""Teaching model for coverage and capacity; executed in the notebook namespace."""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon, Circle
from matplotlib.lines import Line2D
import matplotlib.patches as mpatches
import matplotlib.image as mpimg  # for background images

def draw_hexagonal_cells(
    cell_radius_m,
    grid_extent_m=3000,
    city_diameter_m=5000,
    city_center=(0.0, 0.0),   # in the same meter coords as the grid
    user_density=5,           # just to set the title
    limiting=None,  # scenario-wide limiting constraint
    face_alpha=.7,
    # background options
    background_fit="axes",        # "axes" or "city"
    background_alpha=1.0,         # image transparency
    background_origin="upper",    # "upper" or "lower"
    background_image_path="../../.admin/notebooks/picture/zurich_map.jpg",  # your map
):
    if limiting is None:
        limiting = "coverage" if d_coverage <= d_capacity else "capacity"
    cx, cy = city_center
    city_R = city_diameter_m / 2.0

    fig, ax = plt.subplots(figsize=(5, 5), dpi=160)
    ax.set_aspect('equal')

    # ---- Background image (under everything) ----
    if background_image_path is not None:
        try:
            img = mpimg.imread(background_image_path)
            if background_fit == "city":
                extent = [cx - city_R, cx + city_R, cy - city_R, cy + city_R]
            else:  # "axes"
                extent = [-grid_extent_m, grid_extent_m, -grid_extent_m, grid_extent_m]
            ax.imshow(img, extent=extent, origin=background_origin, alpha=background_alpha, interpolation='none', zorder=0)
        except Exception as e:
            print(f"[warn] Could not load background image: {e}")

    dx = 1.5 * cell_radius_m
    dy = np.sqrt(3) * cell_radius_m

    nx = int(np.ceil(grid_extent_m / dx)) + 2
    ny = int(np.ceil(grid_extent_m / dy)) + 2

    # Counters for legend
    normal_count = 0
    highlight_count = 0

    for i in range(-nx, nx + 1):
        col_offset = (i % 2) * (dy / 2.0)
        for j in range(-ny, ny + 1):
            x = i * dx
            y = j * dy + col_offset

            # keep only hex centers inside the circular boundary
            if (x - cx)**2 + (y - cy)**2 <= city_R**2:
                if limiting == 'coverage':
                    hex_color = 'green'
                    highlight_count += 1
                else:
                    hex_color = 'blue'
                    normal_count += 1

                hexagon = RegularPolygon(
                    (x, y),
                    numVertices=6,
                    radius=cell_radius_m,
                    orientation=np.radians(30),
                    facecolor=hex_color,
                    alpha=face_alpha,
                    edgecolor='black',
                    linewidth=0.5,
                    label=None  # avoid per-cell legend entries
                )
                hexagon.set_zorder(2)
                ax.add_patch(hexagon)

    # City boundary
    boundary = Circle(
        (cx, cy),
        radius=city_R,
        fill=False,
        edgecolor='red',
        linewidth=2.0
    )
    boundary.set_zorder(3)
    ax.add_patch(boundary)

    # Axes, labels, title
    ax.set_xlim(-grid_extent_m, grid_extent_m)
    ax.set_ylim(-grid_extent_m, grid_extent_m)
    ax.set_facecolor((0.2, 0.2, 0.3))
    ax.set_title(f"{limiting.capitalize()} limited: radius {cell_radius_m:.0f} m")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.grid(True, linestyle='--', alpha=.3)

    # --- Custom legend with counts ---
    handles = []
    if normal_count > 0:
        handles.append(mpatches.Patch(facecolor='blue', edgecolor='black',
                                      label=f"Capacity limited, {normal_count} cell(s)"))
    if highlight_count > 0:
        handles.append(mpatches.Patch(facecolor='green', edgecolor='black',
                                      label=f"Coverage limited, {highlight_count} cell(s)"))
    # Boundary proxy (red line) for legend
    handles.append(Line2D([0], [0], color='red', lw=2, label="City of Zurich"))

    ax.legend(handles=handles, prop={"family": "DejaVu Sans", "size": 10},
              fancybox=True, framealpha=1, loc="upper right",
              facecolor=(0.6, 0.61, 0.8))

    plt.tight_layout()
    # Keep labels and cell boundaries as vectors in notebook outputs.
    from io import StringIO
    from IPython.display import SVG, display
    output = StringIO()
    fig.savefig(output, format='svg', bbox_inches='tight')
    plt.close(fig)
    display(SVG(output.getvalue()))

# Functions to compute coverage and capacity-limited radius
def coverage_radius(tx_power, rx_sensitivity, frequency, antenna_gain):
    fspl = tx_power + 2 * antenna_gain - rx_sensitivity  # Free-space path loss
    wavelength = speed_of_light / frequency
    radius = 10 ** ((fspl - 20 * np.log10(4 * np.pi / wavelength)) / 20)
    return radius

def capacity_radius(user_density, data_rate_per_user, bandwidth, sinr_linear):
    total_demand = user_density * data_rate_per_user  # bps per km^2
    cell_capacity = bandwidth * np.log2(1 + sinr_linear)  # bps
    if total_demand>0:
        cell_area = cell_capacity / total_demand  # km^2
    else:
        cell_area = float("inf")
    radius = np.sqrt(2 * cell_area / (3 * np.sqrt(3))) * 1000  # Hexagon center-to-vertex radius, meters
    return radius


def network_planning_summary():
    """
    Prints a formatted summary using the global variables:
      - tx_power               (dBm)
      - user_density           (users/km²)
      - data_rate_per_user     (bit/s)
      - bandwidth              (Hz)

    Call with no arguments after defining those names somewhere in your notebook.
    """
    need = ["tx_power", "user_density", "data_rate_per_user", "bandwidth"]
    g = globals()
    missing = [n for n in need if n not in g]
    if missing:
        raise NameError(
            "Missing required variables: " + ", ".join(missing) +
            ". Please define them (e.g., tx_power=23.0, user_density=1500, data_rate_per_user=5e6, bandwidth=20e6)."
        )

    tx_power = g["tx_power"]
    user_density = g["user_density"]
    data_rate_per_user = g["data_rate_per_user"]
    bandwidth = g["bandwidth"]
    
    print(f"(1) Transmit power (Tx): {tx_power:.2f} dBm")
    print(f"(2) User density: {user_density:.0f} users/km^2")
    print(f"(3) Target data rate per user: {data_rate_per_user/1e6:.2f} Mb/s")
    print(f"(4) Channel bandwidth: {bandwidth/1e6:.2f} MHz")
    print(f"Coverage radius: {g['d_coverage']:.0f} m | Capacity radius: {g['d_capacity']:.0f} m")
    print(f"Selected radius: {g['d_cell']:.0f} m ({'coverage' if g['d_coverage'] <= g['d_capacity'] else 'capacity'} limited)")
    

def compute_radio_planning(update_globals: bool = True):
    """
    Uses globals already defined in the notebook (no checks) to compute
    link budget & capacity/coverage metrics, and returns a dict.

    Expects these globals to exist:
      tx_power, user_density, data_rate_per_user, bandwidth,
      frequency, speed_of_light, rx_sensitivity, noise_power_density,
      antenna_gain, sinr_target,
      db_to_linear, linear_to_db, fspl_db,
      coverage_radius, capacity_radius
    """
    g = globals()

    # pull from globals (assumes they exist)
    tx_power            = g["tx_power"]
    user_density        = g["user_density"]
    data_rate_per_user  = g["data_rate_per_user"]
    bandwidth           = g["bandwidth"]
    frequency           = g["frequency"]
    speed_of_light      = g["speed_of_light"]
    rx_sensitivity      = g["rx_sensitivity"]
    noise_power_density = g["noise_power_density"]
    antenna_gain        = g["antenna_gain"]
    sinr_target         = g["sinr_target"]

    db_to_linear_fn     = g["db_to_linear"]
    linear_to_db_fn     = g["linear_to_db"]
    fspl_db_fn          = g["fspl_db"]

    coverage_radius_fn  = g["coverage_radius"]
    capacity_radius_fn  = g["capacity_radius"]

    import math, numpy as np

    # wavelength
    wavelength = speed_of_light / frequency

    # FSPL helpers
    f_MHz = frequency / 1e6
    fspl_100m = fspl_db_fn(f_MHz, 0.1)  # 100 m
    fspl_1km  = fspl_db_fn(f_MHz, 1.0)  # 1 km

    # Thermal noise floor over the occupied bandwidth (ideal)
    noise_floor_dbm = noise_power_density + 10 * math.log10(bandwidth)

    # Required received power to hit the SINR target (assuming negligible interference)
    required_rx_power_dbm = noise_floor_dbm + sinr_target

    # Simple link budget (same antenna gain at Tx and Rx; no other losses)
    total_antenna_gain = antenna_gain + antenna_gain  # dB
    rx_power_100m = tx_power + total_antenna_gain - fspl_100m
    rx_power_1km  = tx_power + total_antenna_gain - fspl_1km

    margin_100m = rx_power_100m - required_rx_power_dbm
    margin_1km  = rx_power_1km  - required_rx_power_dbm

    # Max free-space range where link budget meets the SINR target (very idealized)
    fspl_max = tx_power + total_antenna_gain - required_rx_power_dbm
    d_km_max = 10 ** ((fspl_max - 32.44 - 20*math.log10(f_MHz)) / 20)

    # Shannon capacity at SINR target (upper bound)
    sinr_linear = db_to_linear_fn(sinr_target)
    shannon_spectral_eff = math.log2(1 + sinr_linear)       # bits/s/Hz
    shannon_capacity_bps = bandwidth * shannon_spectral_eff # bps

    # Rough demand & users supported at target rate
    per_km2_demand_bps = user_density * data_rate_per_user
    users_supported_at_target = shannon_capacity_bps / data_rate_per_user

    # Alternative noise power (mW) if you need it in linear
    noise_power_mw = 10 ** ((noise_power_density + 10 * np.log10(bandwidth)) / 10)

    # Coverage & capacity radii (your own functions)
    d_coverage = coverage_radius_fn(tx_power, rx_sensitivity, frequency, antenna_gain)
    d_capacity = capacity_radius_fn(user_density, data_rate_per_user, bandwidth, sinr_linear)
    d_cell = min(d_coverage, d_capacity)

    results = {
        "wavelength_m": wavelength,
        "f_MHz": f_MHz,
        "fspl_100m_db": fspl_100m,
        "fspl_1km_db": fspl_1km,
        "noise_floor_dbm": noise_floor_dbm,
        "required_rx_power_dbm": required_rx_power_dbm,
        "total_antenna_gain_db": total_antenna_gain,
        "rx_power_100m_dbm": rx_power_100m,
        "rx_power_1km_dbm": rx_power_1km,
        "margin_100m_db": margin_100m,
        "margin_1km_db": margin_1km,
        "fspl_max_db": fspl_max,
        "d_km_max": d_km_max,
        "sinr_linear": sinr_linear,
        "shannon_spectral_eff_bphz": shannon_spectral_eff,
        "shannon_capacity_bps": shannon_capacity_bps,
        "per_km2_demand_bps": per_km2_demand_bps,
        "users_supported_at_target": users_supported_at_target,
        "noise_power_mw": noise_power_mw,
        "d_coverage_m": d_coverage,
        "d_capacity_m": d_capacity,
        "d_cell_m": d_cell,
    }

    if update_globals:
        g.update({
            "wavelength": wavelength,
            "f_MHz": f_MHz,
            "fspl_100m": fspl_100m,
            "fspl_1km": fspl_1km,
            "noise_floor_dbm": noise_floor_dbm,
            "required_rx_power_dbm": required_rx_power_dbm,
            "total_antenna_gain": total_antenna_gain,
            "rx_power_100m": rx_power_100m,
            "rx_power_1km": rx_power_1km,
            "margin_100m": margin_100m,
            "margin_1km": margin_1km,
            "fspl_max": fspl_max,
            "d_km_max": d_km_max,
            "shannon_spectral_eff": shannon_spectral_eff,
            "shannon_capacity_bps": shannon_capacity_bps,
            "per_km2_demand_bps": per_km2_demand_bps,
            "users_supported_at_target": users_supported_at_target,
            "noise_power": noise_power_mw,
            "sinr_linear": sinr_linear,
            "d_coverage": d_coverage,
            "d_capacity": d_capacity,
            "d_cell": d_cell,
        })
    return results



frequency = 2.4e9          # Hz (e.g., 2.4 GHz)
speed_of_light = 3e8       # m/s
rx_sensitivity = -80       # dBm
noise_power_density = -174 # dBm/Hz (thermal noise at ~290K)
antenna_gain = 0           # dBi (per end; simple assumption)
sinr_target = 10           # dB (target SINR)

import math

def db_to_linear(db): 
    return 10**(db/10)

def linear_to_db(x): 
    return 10*math.log10(x)

# Free-space path loss (FSPL) helper: frequency in MHz, distance in km
def fspl_db(f_MHz, d_km):
    return 32.44 + 20*math.log10(f_MHz) + 20*math.log10(d_km)

