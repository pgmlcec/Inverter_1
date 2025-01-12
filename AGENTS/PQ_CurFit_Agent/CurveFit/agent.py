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

def ECurveFit_factory(config_path, **kwargs):
    try:
        # Load the configuration from the specified path
        config = utils.load_config(config_path)
    except Exception as e:
        agent_logger.error(f"Failed to load configuration: {e}")
        config = {}

    if not config:
        agent_logger.warning("Using default configuration settings.")

    # Read values from the configuration or set defaults
    db_path = config.get('db_path', '~/Log_Files/inverter_operations.db')
    file_path = config.get('file_path', '~/Log_Files/register_data_log.txt')
    curvefitfig_path = config.get('curvefitfig_path', '~/Log_Files/curvefit.png')
    remote_input_file = config.get('remote_input_file','~/DSO_IN/RemoteInputs.txt')
    default_pf = float(config.get('default_pf', 0.5))
    ESC_SOC_Limit = int(config.get('ESC_SOC_Limit', 25))
    inverter_rated_S = int(config.get('inverter_rated_S', 11000))
    normalizing_voltage = int(config.get('normalizing_voltage', 120))
    max_iter_ESC_Vltg_Reg = int(config.get('max_iter_ESC_Vltg_Reg', 100))
    ESC_Step_Time = int(config.get('ESC_Step_Time', 2))
    SOC_UP_VltReg_Limit = int(config.get('SOC_UP_VltReg_Limit', 25))
    SOC_DN_VltReg_Limit = int(config.get('SOC_DN_VltReg_Limit', 95))

    # Log the values read from the configuration
    agent_logger.info("Configuration values loaded:")
    agent_logger.info(f"DB Path: {db_path}")
    agent_logger.info(f"File Path: {file_path}")
    agent_logger.info(f"Curve Fit Path: {curvefitfig_path}")
    agent_logger.info(f"Remote Input file Path: {remote_input_file}")
    agent_logger.info(f"Default Power Factor: {default_pf}")
    agent_logger.info(f"ESC SOC Limit: {ESC_SOC_Limit}")
    agent_logger.info(f"Inverter Rated S: {inverter_rated_S}")
    agent_logger.info(f"Normalizing Voltage: {normalizing_voltage}")
    agent_logger.info(f"Max ESC Voltage Regulation Iterations: {max_iter_ESC_Vltg_Reg}")
    agent_logger.info(f"ESC Step Time: {ESC_Step_Time}")
    agent_logger.info(f"SOC Upper Voltage Limit: {SOC_UP_VltReg_Limit}")
    agent_logger.info(f"SOC Lower Voltage Limit: {SOC_DN_VltReg_Limit}")

    # Pass the loaded configuration values to the ESC agent
    return ECurveFit(
        db_path=db_path,
        file_path=file_path,
        curvefitfig_path=curvefitfig_path,
        remote_input_file=remote_input_file,
        default_pf=default_pf,
        ESC_SOC_Limit=ESC_SOC_Limit,
        inverter_rated_S=inverter_rated_S,
        normalizing_voltage=normalizing_voltage,
        max_iter_ESC_Vltg_Reg=max_iter_ESC_Vltg_Reg,
        ESC_Step_Time=ESC_Step_Time,
        SOC_UP_VltReg_Limit=SOC_UP_VltReg_Limit,
        SOC_DN_VltReg_Limit=SOC_DN_VltReg_Limit,
        **kwargs
    )

class ECurveFit(Agent):

    def __init__(self, db_path, file_path, curvefitfig_path, remote_input_file, default_pf, ESC_SOC_Limit,
                 inverter_rated_S, normalizing_voltage, max_iter_ESC_Vltg_Reg,
                 ESC_Step_Time, SOC_UP_VltReg_Limit, SOC_DN_VltReg_Limit, **kwargs):
        super(ECurveFit, self).__init__(**kwargs)

        # Assign configuration values to instance variables
        self.db_path = os.path.expanduser(db_path)
        self.file_path = os.path.expanduser(file_path)
        self.curvefitfig_path = os.path.expanduser(curvefitfig_path)
        self.remote_input_file = os.path.expanduser(remote_input_file)
        self.default_pf = default_pf
        self.ESC_SOC_Limit = ESC_SOC_Limit
        self.inverter_rated_S = inverter_rated_S
        self.normalizing_voltage = normalizing_voltage
        self.max_iter_ESC_Vltg_Reg = max_iter_ESC_Vltg_Reg
        self.ESC_Step_Time = ESC_Step_Time
        self.SOC_UP_VltReg_Limit = SOC_UP_VltReg_Limit
        self.SOC_DN_VltReg_Limit = SOC_DN_VltReg_Limit

        # Log initialization
        agent_logger.info("ESC Agent initialized with configuration:")
        agent_logger.info(f"DB Path: {self.db_path}")
        agent_logger.info(f"File Path: {self.file_path}")
        agent_logger.info(f"Curve Fit Path: {self.curvefitfig_path}")
        agent_logger.info(f"Curve Fit Path: {self.remote_input_file}")
        agent_logger.info(f"Default Power Factor: {self.default_pf}")
        agent_logger.info(f"ESC SOC Limit: {self.ESC_SOC_Limit}")
        agent_logger.info(f"Inverter Rated S: {self.inverter_rated_S}")
        agent_logger.info(f"Normalizing Voltage: {self.normalizing_voltage}")
        agent_logger.info(f"Max ESC Voltage Regulation Iterations: {self.max_iter_ESC_Vltg_Reg}")
        agent_logger.info(f"ESC Step Time: {self.ESC_Step_Time}")
        agent_logger.info(f"SOC Upper Voltage Limit: {self.SOC_UP_VltReg_Limit}")
        agent_logger.info(f"SOC Lower Voltage Limit: {self.SOC_DN_VltReg_Limit}")


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
            apparent_power = abs(entry['apparent_power'])  # Take absolute value of apparent power
            active_power = abs(entry['active_power'])  # Take absolute value of active power

            # Avoid division by zero in power factor calculation
            if apparent_power != 0:
                power_factor = active_power / apparent_power
                pf_values.append(abs(power_factor))
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
    '''
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
    '''

    # Step 4: Fit the curve and find the optimum voltage (max or min based on direction)
    def find_optimum_pf(self, pf_values, voltage_values, direction):
        agent_logger.info("3...")
        # Fit the quadratic curve
        params, _ = curve_fit(self.quadratic_fit, pf_values, voltage_values)

        # Unpack the quadratic coefficients
        a, b, _ = params

        # Find the optimum power factor by setting the derivative to zero
        optimum_pf = -b / (2 * a)

        # Depending on the direction, find the maximum or minimum
        if direction == 1:  # Find maximum
            if a < 0:  # Ensure the curve opens downwards for a maximum
                optimum_voltage = self.quadratic_fit(optimum_pf, *params)
            else:
                agent_logger.warning("No maximum exists: Curve opens upwards.")
                optimum_voltage = None
        elif direction == -1:  # Find minimum
            if a > 0:  # Ensure the curve opens upwards for a minimum
                optimum_voltage = self.quadratic_fit(optimum_pf, *params)
            else:
                agent_logger.warning("No minimum exists: Curve opens downwards.")
                optimum_voltage = None
        else:
            raise ValueError("Direction must be either +1 (for max) or -1 (for min).")

        return params, optimum_pf, optimum_voltage

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
    def Fit_Curve(self,direction):

        agent_logger.info("RPC call received. Fitting started...")
        data = self.load_data()
        agent_logger.info("1 done..")
        pf_values, voltage_values = self.prepare_data(data)
        params, self.optimum_pf, max_voltage = self.find_optimum_pf(pf_values,voltage_values,direction)

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
        utils.vip_main(ECurveFit_factory, version=__version__)
    except Exception as e:
        agent_logger.exception('Unhandled exception in main')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass


