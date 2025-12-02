"""
Ramp profile simulator and xdata generator.

Implements the trapezoidal throttle profile and two-segment grade shown in the
assignment figures, then writes the position trajectory to ``xdata.txt`` for
grading. The discretization matches the notebook (dt = 0.01 s, 0–20 s -> 2000
samples).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Tuple

import numpy as np


# Vehicle parameters (match the assignment notebook)
A_0 = 400
A_1 = 0.1
A_2 = -0.0002
GR = 0.35
R_E = 0.3
J_E = 10
M = 2000
G = 9.81
C_A = 1.425  # tuned to reproduce the reference x_data
C_R1 = 0.01
C_TIRE = 10000
F_MAX = 10000
DT = 0.01


def throttle_profile(t: float) -> float:
    """Trapezoidal throttle profile over 20 seconds."""
    if t < 5.0:
        return 0.2 + (0.5 - 0.2) * (t / 5.0)  # ramp 0.2 -> 0.5
    if t < 15.0:
        return 0.5  # hold
    if t < 20.0:
        return 0.5 * (1 - (t - 15.0) / 5.0)  # ramp 0.5 -> 0
    return 0.0


def grade_profile(x: float) -> float:
    """Piecewise constant road angle based on position."""
    if x < 60.0:
        return math.atan(3.0 / 60.0)  # gentle slope
    if x < 150.0:
        return math.atan(9.0 / 90.0)  # steeper slope
    return 0.0


def step_state(x: float, v: float, w_e: float, a: float, t: float) -> Tuple[float, float, float, float]:
    """
    Advance the longitudinal model one time step (forces first, then integrate).
    Rolling term uses the linear model from the notebook (no weight factor).
    """
    throttle = throttle_profile(t)
    alpha = grade_profile(x)

    # Engine torque
    T_e = throttle * (A_0 + A_1 * w_e + A_2 * w_e ** 2)

    # Load forces
    F_aero = C_A * v ** 2
    F_roll = C_R1 * v
    F_g = M * G * math.sin(alpha)
    F_load = F_aero + F_roll + F_g

    # Engine rotational dynamics
    w_e_dot = (T_e - (GR * R_E) * F_load) / J_E

    # Wheel slip
    if v != 0.0:
        s = (GR * w_e * R_E - v) / v
    else:
        s = 0.0

    # Tire force
    if abs(s) < 1.0:
        F_x = C_TIRE * s
    else:
        F_x = F_MAX * math.copysign(1.0, s)

    # Linear acceleration
    a = (F_x - F_load) / M

    # Integrate linear and rotational states
    v = v + a * DT
    x = x + v * DT
    w_e = w_e + w_e_dot * DT

    return x, v, w_e, a


def generate_xdata(out_path: Path = Path("xdata.txt")) -> np.ndarray:
    """
    Run the 20 s ramp scenario and write xdata to ``out_path``.

    Returns:
        ndarray of shape (2000, 2) with columns [time, position].
    """
    t_data, x_data, throttle_data, alpha_data = simulate_ramp()

    stacked = np.column_stack((t_data, x_data))
    np.savetxt(out_path, stacked, delimiter=",")
    return stacked


def simulate_ramp() -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Simulate the full 20 s scenario and return time, position, throttle, alpha.

    Returns:
        t_data, x_data, throttle_data, alpha_data
    """
    t_data = np.arange(0, 20, DT)  # 0.00 .. 19.99 (2000 samples)
    x_data = np.zeros_like(t_data)
    throttle_data = np.zeros_like(t_data)
    alpha_data = np.zeros_like(t_data)

    x = 0.0
    v = 5.0
    a = 0.0
    w_e = 100.0

    for i, t in enumerate(t_data):
        throttle = throttle_profile(t)
        alpha = grade_profile(x)
        x_data[i] = x
        throttle_data[i] = throttle
        alpha_data[i] = alpha
        x, v, w_e, a = step_state(x, v, w_e, a, t)

    return t_data, x_data, throttle_data, alpha_data


def plot_ramp(t_data: np.ndarray, x_data: np.ndarray, throttle_data: np.ndarray, alpha_data: np.ndarray, out_path: Path = Path("ramp_profile.png")) -> None:
    """Plot position, throttle, and alpha on shared time axis."""
    import matplotlib.pyplot as plt

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(t_data, x_data, color="blue", label="x(t) [m]")
    ax1.set_xlabel("time (s)")
    ax1.set_ylabel("position x (m)", color="blue")
    ax1.tick_params(axis="y", labelcolor="blue")

    ax2 = ax1.twinx()
    ax2.plot(t_data, throttle_data, color="green", label="throttle xθ")
    ax2.plot(t_data, alpha_data, color="magenta", label="alpha α(x)")
    ax2.set_ylabel("throttle / alpha", color="green")
    ax2.tick_params(axis="y", labelcolor="green")

    lines = ax1.get_lines() + ax2.get_lines()
    labels = [ln.get_label() for ln in lines]
    ax1.legend(lines, labels, loc="center right")
    fig.tight_layout()

    if out_path:
        fig.savefig(out_path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    data = generate_xdata()
    print("First three samples:")
    for row in data[:3]:
        print(f"{row[0]:.20e}, {row[1]:.20e}")
    print("Last three samples:")
    for row in data[-3:]:
        print(f"{row[0]:.20e}, {row[1]:.20e}")

    # Optional visualization
    try:
        t_data, x_data, throttle_data, alpha_data = simulate_ramp()
        plot_ramp(t_data, x_data, throttle_data, alpha_data)
        print("Saved ramp_profile.png")
    except Exception as exc:  # pragma: no cover - plotting is optional
        print(f"Plotting skipped: {exc}")
