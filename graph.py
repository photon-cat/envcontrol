import numpy as np
import matplotlib.pyplot as plt

# decay rate
k = 0.8

# time axis
t = np.linspace(0, 10, 500)

# some initial crosstrack errors (meters)
e0_list = [2.0, 1.0, -1.0, -2.0]

plt.figure(figsize=(8, 5))

for e0 in e0_list:
    # analytical solution to e'(t) = -k e(t)
    e = e0 * np.exp(-k * t)
    plt.plot(t, e, label=f"e₀ = {e0} m")

plt.axhline(0, color='black', linewidth=0.8)
plt.xlabel("time (s)")
plt.ylabel("crosstrack error e(t)")
plt.title("Exponential Decay of Crosstrack Error")
plt.legend()
plt.grid(True)
plt.show()