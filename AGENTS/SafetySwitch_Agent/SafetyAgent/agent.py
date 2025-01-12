__docformat__ = 'reStructuredText'

import logging
import sys
from volttron.platform.agent import utils
import sqlite3
from volttron.platform.vip.agent import Agent, Core, RPC
import os
import time

"""
Setup agent-specific logging
"""
agent_log_file = os.path.expanduser('~/Log_Files/SafetyAgent.log')
agent_logger = logging.getLogger('SafetyAgentLogger')
agent_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(agent_log_file)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
agent_logger.addHandler(file_handler)

utils.setup_logging()
__version__ = '0.1'


def SSwitch_factory(config_path, **kwargs):
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
    return SSwitch(
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

class SSwitch(Agent):

    def __init__(self, db_path, file_path, curvefitfig_path,remote_input_file, default_pf, ESC_SOC_Limit,
                 inverter_rated_S, normalizing_voltage, max_iter_ESC_Vltg_Reg,
                 ESC_Step_Time, SOC_UP_VltReg_Limit, SOC_DN_VltReg_Limit, **kwargs):
        super(SSwitch, self).__init__(**kwargs)

        # Assign configuration values to instance variables
        self.db_path = os.path.expanduser(db_path)
        self.file_path = os.path.expanduser(file_path)
        self.curvefitfig_path = os.path.expanduser(curvefitfig_path)
        self.remote_input_file= os.path.expanduser(remote_input_file)
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


    def write_remote_file_and_set_modes_to_zero(self):
        """Sets all modes to zero while preserving other file content."""
        if os.path.exists(self.remote_input_file):
            try:
                # Read the file content
                with open(self.remote_input_file, 'r') as file:
                    lines = file.readlines()

                # Update the mode lines
                for i, line in enumerate(lines):
                    if line.startswith("fix_power_mode="):
                        lines[i] = "fix_power_mode=0\n"
                    elif line.startswith("voltage_regulation_mode="):
                        lines[i] = "voltage_regulation_mode=0\n"
                    elif line.startswith("ESC_volt_reg_mode="):
                        lines[i] = "ESC_volt_reg_mode=0\n"

                # Write the updated content back to the file
                with open(self.remote_input_file, 'w') as file:
                    file.writelines(lines)

                agent_logger.info(f"Successfully set all modes to zero in {self.remote_input_file}.")
            except IOError as e:
                logger.error(f"Failed to modify file {self.remote_input_file}: {e}")
        else:
            logger.error(f"File {self.remote_input_file} not found.")


    def monitorSS(self):
        """Continuously monitor the allow_opr variable in the operational_data table."""
        agent_logger.info("Starting allow_opr Monitoring...")

        conn = None
        cursor = None
        previous_allow_opr = 0  # Initial assumption

        try:
            # Attempt to connect to the database if not connected
            if conn is None:
                agent_logger.info("Attempting to connect to the database...")
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                agent_logger.info("Connected to database successfully.")
        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {e}")
            return

        while True:
            try:
                # Query to fetch the latest allow_opr status
                query = """
                    SELECT allow_opr 
                    FROM operational_data 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """
                cursor.execute(query)
                result = cursor.fetchone()

                if result:
                    current_allow_opr = result[0]
                    agent_logger.info(f"Current allow_opr status: {current_allow_opr}")

                    # Check if allow_opr has changed from 1 to 0
                    if previous_allow_opr == 1 and current_allow_opr == 0:
                        agent_logger.info("allow_opr changed from 1 to 0. Running necessary scripts...")

                        # Make all modes 0 in script
                        agent_logger.info("Writing all modes to 0")
                        time.sleep(2)
                        self.write_remote_file_and_set_modes_to_zero()
                        time.sleep(2)

                    # Update the previous allow_opr status
                    previous_allow_opr = current_allow_opr
                else:
                    logger.warning("No data found in the operational_data table.")

                # Sleep before the next check
                time.sleep(5)

            except sqlite3.Error as e:
                logger.error(f"Database error: {e}. Retrying connection in 5 seconds...")
                conn = None  # Reset connection to force reconnection
                time.sleep(5)
            except subprocess.CalledProcessError as e:
                logger.error(f"Error while running a script: {e}")
            except Exception as e:
                logger.error(f"Unexpected error: {e}. Retrying in 5 seconds...")
                time.sleep(5)



    @Core.receiver('onstart')
    def on_start(self, sender, **kwargs):
        """Agent start logic."""
        agent_logger.info("Agent started, waiting for 10 seconds before starting operations...")
        time.sleep(2)

        # Start monitoring the inputs for changes
        self.monitorSS()

    @Core.receiver('onstop')
    def on_stop(self, sender, **kwargs):
        """Close the database connection when stopping."""


def main():
    """Main method called to start the agent."""
    try:
        utils.vip_main(SSwitch_factory, version=__version__)
    except Exception as e:
        agent_logger.exception('Unhandled exception in main')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
