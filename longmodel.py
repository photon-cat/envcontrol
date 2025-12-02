"""
Forward longitudinal vehicle model.

The model converts a throttle command (0.0-1.0) and road grade into vehicle
motion by propagating a simplified drivetrain and load-force balance. It
follows the equations described in the accompanying notebook and integrates
them with a fixed sample time.
"""

from __future__ import annotations

import math


class Vehicle:
    """Simple forward longitudinal vehicle model."""

    def __init__(self) -> None:
        # Throttle-to-engine torque
        self.a_0 = 400
        self.a_1 = 0.1
        self.a_2 = -0.0002

        # Gear ratio, effective radius, mass + inertia
        self.GR = 0.35
        self.r_e = 0.3
        self.J_e = 10
        self.m = 2000
        self.g = 9.81

        # Aerodynamic and friction coefficients
        self.c_a = 1.36
        self.c_r1 = 0.01

        # Tire force
        self.c = 10000
        self.F_max = 10000

        # State variables
        self.x = 0.0
        self.v = 5.0
        self.a = 0.0
        self.w_e = 100.0
        self.w_e_dot = 0.0

        self.sample_time = 0.01

    def reset(self) -> None:
        """Reset state variables to their initial values."""
        self.x = 0.0
        self.v = 5.0
        self.a = 0.0
        self.w_e = 100.0
        self.w_e_dot = 0.0

    def step(self, throttle: float, alpha: float):
        """
        Propagate the model forward by one time step.

        Args:
            throttle: Throttle command in [0, 1].
            alpha: Road incline angle in radians (positive = uphill).

        Returns:
            Tuple of updated (x, v, a, w_e, w_e_dot).
        """
        # Clamp throttle to a physically meaningful range
        throttle = max(0.0, min(1.0, float(throttle)))
        alpha = float(alpha)
        dt = self.sample_time

        # Engine torque
        T_e = throttle * (self.a_0 + self.a_1 * self.w_e + self.a_2 * self.w_e ** 2)

        # Load forces
        F_aero = self.c_a * self.v ** 2
        F_roll = self.c_r1 * self.m * self.g * self.v
        F_g = self.m * self.g * math.sin(alpha)
        F_load = F_aero + F_roll + F_g

        # Engine rotational dynamics
        self.w_e_dot = (T_e - (self.GR * self.r_e) * F_load) / self.J_e

        # Wheel slip
        if self.v > 0.0:
            s = (self.GR * self.w_e * self.r_e - self.v) / self.v
        else:
            s = 0.0

        # Tire force
        if abs(s) < 1.0:
            F_x = self.c * s
        else:
            F_x = self.F_max * math.copysign(1.0, s)

        # Linear acceleration
        self.a = (F_x - F_load) / self.m

        # Integrate linear and rotational states (explicit Euler)
        self.v += self.a * dt
        self.x += self.v * dt
        self.w_e += self.w_e_dot * dt

        return self.x, self.v, self.a, self.w_e, self.w_e_dot


if __name__ == "__main__":
    # Basic demonstration with a constant throttle and grade.
    try:
        import numpy as np
    except ImportError:
        np = None

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        plt = None

    model = Vehicle()

    time_end = 100
    if np is not None:
        t_data = np.arange(0, time_end, model.sample_time)
        v_data = np.zeros_like(t_data)
    else:
        steps = int(time_end / model.sample_time)
        t_data = [i * model.sample_time for i in range(steps)]
        v_data = [0.0 for _ in range(steps)]

    throttle = 0.9  # throttle percentage between 0 and 1
    alpha = 0.15  # incline angle in radians

    for i in range(len(t_data)):
        v_data[i] = model.v
        model.step(throttle, alpha)

    if plt is not None:
        plt.plot(t_data, v_data)
        plt.xlabel("Time [s]")
        plt.ylabel("Velocity [m/s]")
        plt.title("Longitudinal Model Velocity Profile")
        plt.show()
    else:
        print(f"Final velocity after {time_end}s: {model.v:.3f} m/s")
