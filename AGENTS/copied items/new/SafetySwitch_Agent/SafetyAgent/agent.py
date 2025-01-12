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


class SSwitch(Agent):
    """
    An agent that sets the SSwitch of the complete system.
    """

    def __init__(self, setting1=1, setting2="some/random/topic", **kwargs):
        # Initialize the agent
        kwargs.pop('config_path', None)
        super(SSwitch, self).__init__(**kwargs)
        agent_logger.info("Agent initialized successfully")
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

        self.remote_input_file = os.path.expanduser('~/DSO_IN/RemoteInputs.txt')

        # Initialize

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
        utils.vip_main(SSwitch, version=__version__)
    except Exception as e:
        agent_logger.exception('Unhandled exception in main')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
