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
agent_log_file = os.path.expanduser('~/Log_Files/OpsAgent.log')
agent_logger = logging.getLogger('OperationLogger')
agent_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(agent_log_file)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
agent_logger.addHandler(file_handler)

utils.setup_logging()
__version__ = '0.1'


def Operations_factory(config_path, **kwargs):
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
    return Operations(
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


class Operations(Agent):
    """
    An agent that sets the operations of the complete system.
    """

    def __init__(self, db_path, file_path, curvefitfig_path,remote_input_file, default_pf, ESC_SOC_Limit,
                 inverter_rated_S, normalizing_voltage, max_iter_ESC_Vltg_Reg,
                 ESC_Step_Time, SOC_UP_VltReg_Limit, SOC_DN_VltReg_Limit, **kwargs):
        super(Operations, self).__init__(**kwargs)

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

        # Initialize placeholders for connection and cursor
        self.conn = None
        self.cursor = None

        # Define initial values for tracking changes
        self.current_remote_input = None
        self.current_local_input = None
        self.current_mode = None

    def connect_to_db(self):
        """Connect to the SQLite database and create cursor."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            agent_logger.info("Connected to the SQLite database successfully")
        except sqlite3.Error as e:
            agent_logger.error(f"Error connecting to SQLite database: {e}")

    def fetch_remote_inputs(self):
        """Fetch the latest remote inputs from the database based on timestamp and return as a dictionary."""
        query = "SELECT * FROM remote_inputs ORDER BY timestamp DESC LIMIT 1"
        try:
            self.cursor.execute(query)
            row = self.cursor.fetchone()
            column_names = [description[0] for description in self.cursor.description]

            if row:
                remote_data = dict(zip(column_names, row))
                agent_logger.info(f"Fetched Latest Remote Inputs: {remote_data}")
                return remote_data
            else:
                agent_logger.info("No data found for remote inputs")
                return None
        except sqlite3.Error as e:
            agent_logger.error(f"Error fetching remote inputs: {e}")
            return None

    def fetch_local_inputs(self):
        """Fetch the latest local inputs from the database based on timestamp and return as a dictionary."""
        query = "SELECT * FROM local_inputs ORDER BY timestamp DESC LIMIT 1"
        try:
            self.cursor.execute(query)
            row = self.cursor.fetchone()
            column_names = [description[0] for description in self.cursor.description]

            if row:
                local_data = dict(zip(column_names, row))
                agent_logger.info(f"Fetched Latest Local Inputs: {local_data}")
                return local_data
            else:
                agent_logger.info("No data found for local inputs")
                return None
        except sqlite3.Error as e:
            agent_logger.error(f"Error fetching local inputs: {e}")
            return None

    def turn_off_voltvar(self):
        """
        Make an RPC call to the Volt_Varagent-0.1_1 peer to turn off VoltVar.
        """
        peer = "Volt_Varagent-0.1_1"
        try:
            # Make the RPC call to the TurnOffVoltvar function on Volt_Varagent-0.1_1
            self.vip.rpc.call(peer, 'TurnOffVoltvar').get(timeout=10)
            agent_logger.info(f"VoltVar is turned off on peer {peer}.")
        except Exception as e:
            agent_logger.error(f"Error during RPC call to {peer}: {str(e)}")

    def turn_off_fix_power(self):
        """
        Make an RPC call to the fix_poweragent-0.1_1 peer to turn off Fix Power mode.
        """
        peer = "FixPQagent-0.1_1"
        try:
            # Make the RPC call to the TurnOffFixPower function on Volt_Varagent-0.1_1
            self.vip.rpc.call(peer, 'turn_off_fix_power').get(timeout=10)
            agent_logger.info(f" Fix Power is turned off on peer {peer}.")
        except Exception as e:
            agent_logger.error(f"Error during RPC call to {peer}: {str(e)}")


    def turn_off_ESCVoltReg(self):

        peer = "ESCVRagent-0.1_1"
        agent_logger.info(f" trying to turn off ESC Volt reg. on peer {peer}.")
        try:
            # Make the RPC call to the TurnOffFixPower function on Volt_Varagent-0.1_1
            self.vip.rpc.call(peer, 'turn_off_ESC_volt_reg').get(timeout=10)
            agent_logger.info(f" ESC Volt reg. is turned off on peer {peer}.")
        except Exception as e:
            agent_logger.error(f"Error during RPC call to {peer}: {str(e)}")


    def run_mode(self, mode):
        """do not make an RPC call to another agent to run the given mode. rather just set variables in DB"""
        if not isinstance(mode, dict):
            agent_logger.error("Mode should be a dictionary, invalid data received")
            return

        if mode.get('voltage_regulation_mode'):
            agent_logger.info("VoltVar mode : 1")
            self.turn_off_fix_power()
            self.turn_off_ESCVoltReg()

        if mode.get('fix_power_mode'):
            agent_logger.info("Fixed Power mode : 1")
            self.turn_off_voltvar()  # Call the function to turn off VoltVar
            self.turn_off_ESCVoltReg()

        if mode.get('ESC_volt_reg_mode'):
            agent_logger.info("ESC Voltage Regulation mode : 1")
            self.turn_off_voltvar()  # Call the function to turn off VoltVar
            self.turn_off_fix_power()

    def update_operational_data(self, allow_opr, mode):
        """Update the operational_data table in the database with values from mode."""
        try:
            # Extract the relevant fields from the mode dictionary
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            data_to_update = {
                'allow_opr': allow_opr,
                'voltage_regulation_mode': mode.get('voltage_regulation_mode'),
                'fix_power_mode': mode.get('fix_power_mode'),
                'ESC_volt_reg_mode': mode.get('ESC_volt_reg_mode'),
                'fix_real_power': mode.get('fix_real_power'),
                'fix_reactive_power': mode.get('fix_reactive_power'),
                'QVVMax': mode.get('QVVMax'),
                'VVVMax_Per': mode.get('VVVMax_Per'),
                'Low_Volt_Lmt': mode.get('Low_Volt_Lmt'),
                'High_Volt_Lmt': mode.get('High_Volt_Lmt'),
                'ESC_VA': mode.get('ESC_VA'),
                'ESC_VA_steps': mode.get('ESC_VA_steps'),
                'ESC_Repeat_Time': mode.get('ESC_Repeat_Time')
            }

            # Construct the query to update the operational_data table
            columns = ', '.join(data_to_update.keys())
            placeholders = ', '.join('?' * len(data_to_update))
            query = f"INSERT INTO operational_data (timestamp, {columns}) VALUES (?, {placeholders})"

            # Log the data for debugging
            agent_logger.info(f"Updating operational_data with: {data_to_update}")

            # Execute the query
            self.cursor.execute(query, (timestamp, *data_to_update.values()))
            self.conn.commit()
        except sqlite3.Error as e:
            agent_logger.error(f"Error updating operational_data: {e}")

    def enforce_mutual_exclusivity(self, mode):
        """Ensure only one mode is active, prioritize fix_power."""
        agent_logger.info("Checking for mutual exclusivity between volt_var, fix_power, and ESC volt_reg modes")

        if not isinstance(mode, dict):
            agent_logger.error("Mode should be a dictionary, invalid data received")
            return mode

        # If both voltage regulation and fixed power modes are active, prioritize fixed power
        if mode.get('voltage_regulation_mode') == 1 and mode.get('fix_power_mode') == 1:
            agent_logger.info("Both voltage regulation and fix power modes active, so Fix Power prioritized over Voltage Regulation")
            mode['voltage_regulation_mode'] = 0  # Disable VoltVar if fix_power is also on

        # Handle ESC voltage regulation mode
        if mode.get('ESC_volt_reg_mode') == 1 and mode.get('fix_power_mode') == 1:
            mode['ESC_volt_reg_mode'] = 0  # Disable ESC if fix_power is also on
            agent_logger.info("ESC-VOltReg and Fix power active , prioritizing Fix Power")

        return mode

    def check_mode(self, remote_inputs, local_inputs):
        """Check which mode to run based on remote and local inputs."""
        agent_logger.info("Checking mode between remote and local inputs")

        if remote_inputs is not None:
            if remote_inputs['voltage_regulation_mode'] == 1:
                self.current_mode = "Remote Voltage Regulation Mode"
                agent_logger.info("Remote Voltage Regulation Mode is active")
                return remote_inputs
            elif remote_inputs['fix_power_mode'] == 1:
                self.current_mode = "Remote Fix Power Mode"
                agent_logger.info("Remote Fix Power Mode is active")
                return remote_inputs
            elif remote_inputs['ESC_volt_reg_mode'] == 1:
                self.current_mode = "Remote ESC Voltage Regulation Mode"
                agent_logger.info("Remote ESC Voltage Regulation Mode is active")
                return remote_inputs

        if local_inputs is not None:
            if local_inputs['voltage_regulation_mode'] == 1:
                self.current_mode = "Local Voltage Regulation Mode"
                agent_logger.info("Local Voltage Regulation Mode is active")
                return local_inputs
            elif local_inputs['fix_power_mode'] == 1:
                self.current_mode = "Local Fix Power Mode"
                agent_logger.info("Local Fix Power Mode is active")
                return local_inputs
            elif local_inputs['ESC_volt_reg_mode'] == 1:
                self.current_mode = "Local ESC Voltage Regulation Mode"
                agent_logger.info("Local ESC Voltage Regulation Mode is active")
                return local_inputs

        agent_logger.info("No mode is active. Returning local states to operation.")

        # If no mode is active in both remote and local inputs
        agent_logger.info("VoltVar, Fix Power, ESC volt reg modes are 0.")
        self.turn_off_voltvar()  # Turn off VoltVar
        self.turn_off_fix_power()  # Turn off Fix Power
        self.turn_off_ESCVoltReg()
        return local_inputs

    def monitor_changes(self):
        """Monitor changes in RemoteInputs and LocalInputs and act accordingly."""
        while True:
            agent_logger.info(f"Monitoring changes to mode operation")
            try:
                remote_inputs = self.fetch_remote_inputs()
                local_inputs = self.fetch_local_inputs()

                # Check mode and prioritize remote inputs
                mode = self.check_mode(remote_inputs, local_inputs)

                if mode:
                    # Enforce mutual exclusivity between modes
                    mode = self.enforce_mutual_exclusivity(mode)
                    allow = self.check_switch()
                    self.run_mode(mode)
                    self.update_operational_data(allow_opr=allow, mode=mode)

                time.sleep(4)  # Monitor every 2 seconds for changes
            except Exception as e:
                agent_logger.error(f"Error in monitoring changes: {e}")
                time.sleep(2)  # Continue monitoring after a delay

    def check_switch(self):
        """
        Check if the conditions in the database are met:
        inverter_status = 3, modbus_comm = 1, master_switch = 1.
        Returns True if all conditions are satisfied, False otherwise.
        """
        try:
            # Query the most recent row from inverter_registers (based on timestamp)
            self.cursor.execute('''
                SELECT inverter_status 
                FROM inverter_registers 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''')
            inverter_status_row = self.cursor.fetchone()

            # Query the most recent row from safety_data (based on timestamp)
            self.cursor.execute('''
                SELECT modbus_comm, master_switch 
                FROM safety_data 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''')
            safety_data_row = self.cursor.fetchone()

            # Check if both queries returned data
            if inverter_status_row is None or safety_data_row is None:
                agent_logger.error("Data not found in one or both tables")
                return False

            # Extract the results and log the fetched data
            inverter_status = inverter_status_row[0]
            modbus_comm, master_switch = safety_data_row

            # Log the fetched values for debugging
            agent_logger.info(f"Fetched inverter_status: {inverter_status}")
            agent_logger.info(f"Fetched modbus_comm: {modbus_comm}, master_switch: {master_switch}")

            # Check if the conditions are met
            if inverter_status == 3 and modbus_comm == 1 and master_switch == 1:
                agent_logger.info("Conditions met: inverter_status = 3, modbus_comm = 1, master_switch = 1")
                return True
            else:
                agent_logger.info("Conditions not met")
                return False

        except sqlite3.Error as e:
            agent_logger.error(f"Error querying the database: {e}")
            return False

    @Core.receiver('onstart')
    def on_start(self, sender, **kwargs):
        """Agent start logic."""
        agent_logger.info("Agent started, waiting for 10 seconds before starting operations...")
        time.sleep(10)

        # Connect to the database
        self.connect_to_db()

        # Fetch initial data
        remote_inputs = self.fetch_remote_inputs()
        local_inputs = self.fetch_local_inputs()
        agent_logger.info(f"Initial data fetched: Remote Inputs, Local Inputs")

        # Check the initial mode and run it
        mode = self.check_mode(remote_inputs, local_inputs)

        if mode:
            # Enforce mutual exclusivity between volt_var, fix_power, and ESC voltage regulation modes
            mode = self.enforce_mutual_exclusivity(mode)
            allow = self.check_switch()
            self.run_mode(mode)
            self.update_operational_data(allow_opr=allow, mode=mode)

        # Start monitoring the inputs for changes
        self.monitor_changes()

    @Core.receiver('onstop')
    def on_stop(self, sender, **kwargs):
        """Close the database connection when stopping."""
        if self.conn:
            self.conn.close()
            agent_logger.info("Database connection closed")


def main():
    """Main method called to start the agent."""
    try:
        utils.vip_main(Operations_factory, version=__version__)
    except Exception as e:
        agent_logger.exception('Unhandled exception in main')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
