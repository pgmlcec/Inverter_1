import json
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt


# Step 1: Load the data from a JSON file
def load_data(filename):
    data = []
    with open(filename, 'r') as file:
        for line in file:
            data.append(json.loads(line.strip()))
    return data


# Step 2: Calculate power factor and prepare data for curve fitting
def prepare_data(data):
    pf_values = []
    voltage_values = []
    for entry in data:
        apparent_power = entry['apparent_power']
        active_power = entry['active_power']

        # Avoid division by zero in power factor calculation
        if apparent_power != 0:
            power_factor = active_power / apparent_power
            pf_values.append(power_factor)
            voltage_values.append(entry['a_phase_voltage'])
    return np.array(pf_values), np.array(voltage_values)


# Step 3: Define a fitting function, e.g., quadratic fit for simplicity
def quadratic_fit(x, a, b, c):
    return a * x ** 2 + b * x + c


# Step 4: Fit the curve and find the maximum voltage
def find_optimum_pf(pf_values, voltage_values):
    # Fit the quadratic curve
    params, _ = curve_fit(quadratic_fit, pf_values, voltage_values)

    # Find the optimum power factor by setting the derivative to zero
    a, b, _ = params
    optimum_pf = -b / (2 * a)
    max_voltage = quadratic_fit(optimum_pf, *params)

    return params, optimum_pf, max_voltage


# Step 5: Plot data points and fitted curve
def plot_curve(pf_values, voltage_values, params):
    plt.scatter(pf_values, voltage_values, color='blue', label='Data Points')

    # Generate a smooth curve for the fit
    x_fit = np.linspace(min(pf_values), max(pf_values), 100)
    y_fit = quadratic_fit(x_fit, *params)

    plt.plot(x_fit, y_fit, color='red', label='Fitted Curve')
    plt.xlabel('Power Factor')
    plt.ylabel('A Phase Voltage')
    plt.title('Curve Fitting for Maximum Voltage vs. Power Factor')
    plt.legend()
    plt.show()


# Main function
def main(filename):
    filename = 'register_data_log.txt'  # Replace with your actual file path
    data = load_data(filename)
    pf_values, voltage_values = prepare_data(data)
    params, optimum_pf, max_voltage = find_optimum_pf(pf_values, voltage_values)

    print("Optimum Power Factor:", optimum_pf)
    print("Maximum Voltage at Optimum PF:", max_voltage)

    # Plot the data and fitted curve
    plot_curve(pf_values, voltage_values, params)


# Example usage
filename = 'register_data_log.txt'  # Replace with your actual file path
main(filename)
