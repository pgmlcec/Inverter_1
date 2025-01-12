__docformat__ = 'reStructuredText'

import logging
import sys
from volttron.platform.agent import utils
import sqlite3
from volttron.platform.vip.agent import Agent, Core, RPC
import os
import time
import json
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt


"""
Setup agent-specific logging
"""
agent_log_file = os.path.expanduser('~/Log_Files/ECurveFit.log')
agent_logger = logging.getLogger('ECurveFitLogger')
agent_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(agent_log_file)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
agent_logger.addHandler(file_handler)

utils.setup_logging()
__version__ = '0.1'


class ECurveFit(Agent):

    def __init__(self, setting1=1, setting2="some/random/topic", **kwargs):
        # Initialize the agent
        kwargs.pop('config_path', None)
        super(ECurveFit, self).__init__(**kwargs)
        agent_logger.info("valid agent initialization")
        self.setting1 = setting1
        self.setting2 = setting2
        self.default_config = {"setting1": setting1, "setting2": setting2}
        self.vip.config.set_default("config", self.default_config)

        # Later move to config
        self.db_path = os.path.expanduser('~/Log_Files/inverter_operations.db')  # Update path as necessary
        self.file_path = os.path.expanduser('~/Log_Files/register_data_log.txt')
        self.curvefitfig_path = os.path.expanduser(f"~/Log_Files/curvefit.png")
        self.default_pf = 0.5
        self.ESC_SOC_Limit=25
        self.inverter_rated_S = 11000
        self.normalizing_voltage = 120
        self.max_iter_ESC_Vltg_Reg = 100
        self.ESC_Step_Time = 2
        self.SOC_UP_VltReg_Limit = 25
        self.SOC_DN_VltReg_Limit = 95



        self.optimum_pf= 0.5
# Initialize placeholders for the database connection and cursor
        self.conn = None
        self.cursor = None

        # Connect to the database
        agent_logger.info(f"trying connecting to data base")
        self.connect_to_db()


    def connect_to_db(self):
        """Connect to the SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            agent_logger.info("Connected to the SQLite database successfully")
        except sqlite3.Error as e:
            agent_logger.error(f"Error connecting to SQLite database: {e}")

    def Update_DB_ActReac_Ratio(self):

        if not (0 <= self.optimum_pf <= 1):
            agent_logger.warning(f"optimum_pf value {self.optimum_pf} is out of range. Resetting to 0.5.")
            self.optimum_pf = 0.5

        try:
            # Check if self.optimum_pf is valid
            if self.optimum_pf is not None:
                # SQL query to update the Act_Reac_Ratio column
                update_query = """
                    UPDATE ESC_data
                    SET Act_Reac_Ratio = ?
                    WHERE rowid = 1
                """
                agent_logger.info(f"Updating Act_Reac_Ratio in ESC_data table with value: {self.optimum_pf}")

                # Execute the update query
                self.cursor.execute(update_query, (self.optimum_pf,))
                self.conn.commit()
                agent_logger.info("Successfully updated Act_Reac_Ratio in ESC_data table.")
            else:
                agent_logger.warning("optimum_pf is None. Cannot update Act_Reac_Ratio in ESC_data table.")

        except sqlite3.Error as e:
            agent_logger.error(f"Error updating Act_Reac_Ratio in ESC_data table: {e}")


    # Step 1: Load the data from a JSON file
    def load_data(self):
        agent_logger.info("1...")
        data = []
        with open(self.file_path, 'r') as file:
            for line in file:
                data.append(json.loads(line.strip()))
        return data

    # Step 2: Calculate power factor and prepare data for curve fitting
    def prepare_data(self, data):
        agent_logger.info("2...")
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

    def prepare_data(self, data):

        agent_logger.info("Preparing data for curve fitting...")
        INVERTER_RATED_POWER= self.inverter_rated_S
        pf_values = []
        voltage_values = []

        for entry in data:
            apparent_power = entry['apparent_power']
            active_power = entry['active_power']
            voltage = entry['a_phase_voltage']

            # Check for invalid data points
            if apparent_power <= 0:
                agent_logger.warning(f"Skipping entry with invalid apparent power: {apparent_power}")
                continue

            if active_power > apparent_power:
                agent_logger.warning(
                    f"Skipping entry where active power ({active_power} W) exceeds apparent power ({apparent_power} VA).")
                continue

            if apparent_power > INVERTER_RATED_POWER:
                agent_logger.warning(
                    f"Skipping entry where apparent power ({apparent_power} VA) exceeds inverter rated power ({INVERTER_RATED_POWER} VA).")
                continue

            # Calculate power factor
            power_factor = active_power / apparent_power

            # Store valid values
            pf_values.append(power_factor)
            voltage_values.append(voltage)

        agent_logger.info(f"Filtered data size: {len(pf_values)} entries.")
        return np.array(pf_values), np.array(voltage_values)

    # Step 3: Define a fitting function, e.g., quadratic fit for simplicity
    def quadratic_fit(self, x, a, b, c):
        return a * x ** 2 + b * x + c

    # Step 4: Fit the curve and find the maximum voltage
    def find_optimum_pf(self, pf_values, voltage_values):
        agent_logger.info("3...")
        # Fit the quadratic curve
        params, _ = curve_fit(self.quadratic_fit, pf_values, voltage_values)

        # Find the optimum power factor by setting the derivative to zero
        a, b, _ = params
        optimum_pf = -b / (2 * a)
        max_voltage = self.quadratic_fit(optimum_pf, *params)

        return params, optimum_pf, max_voltage

    # Step 5: Plot data points and fitted curve
    def plot_curve(self, pf_values, voltage_values, params):
        agent_logger.info("4...")
        plt.scatter(pf_values, voltage_values, color='blue', label='Data Points')

        # Generate a smooth curve for the fit
        x_fit = np.linspace(min(pf_values), max(pf_values), 100)
        y_fit = self.quadratic_fit(x_fit, *params)

        plt.plot(x_fit, y_fit, color='red', label='Fitted Curve')
        plt.xlabel('Power Factor')
        plt.ylabel('A Phase Voltage')
        plt.title('Curve Fitting for Maximum Voltage vs. Power Factor')
        plt.legend()

        # Save the plot to the specified file path
        plt.savefig(self.curvefitfig_path)
        agent_logger.info(f"Plot saved to {self.curvefitfig_path}")

        # Clear the figure to free memory for subsequent plots
        plt.close()
        #plt.show()

    @RPC.export
    def Fit_Curve(self):

        agent_logger.info("RPC call received. Fitting started...")
        data = self.load_data()
        agent_logger.info("1 done..")
        pf_values, voltage_values = self.prepare_data(data)
        params, self.optimum_pf, max_voltage = self.find_optimum_pf(pf_values,voltage_values)

        print("Optimum Power Factor:", self.optimum_pf)
        print("Maximum Voltage at Optimum PF:", max_voltage)

        # Plot the data and fitted curve
        self.plot_curve(pf_values, voltage_values, params)
        # Update DB
        agent_logger.info("5...")
        self.Update_DB_ActReac_Ratio()
        agent_logger.info("RPC Call completed")


    @Core.receiver('onstart')
    def on_start(self, sender, **kwargs):
        """Agent startup logic."""
        agent_logger.info("Curve Fitting Agent started")
        time.sleep(1)


def main():
    """Main method called to start the agent."""
    try:
        utils.vip_main(ECurveFit, version=__version__)
    except Exception as e:
        agent_logger.exception('Unhandled exception in main')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass


