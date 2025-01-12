__docformat__ = 'reStructuredText'

import logging
import sys
from volttron.platform.agent import utils
import sqlite3
from volttron.platform.vip.agent import Agent, Core, RPC
import os
import time
import csv
import struct
import json
import math
from gevent import Timeout
import datetime

"""
Setup agent-specific logging
"""
agent_log_file = os.path.expanduser('~/Log_Files/ESCVR.log')
agent_logger = logging.getLogger('ESCVRLogger')
agent_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(agent_log_file)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
agent_logger.addHandler(file_handler)

utils.setup_logging()
__version__ = '0.1'

def escvr_factory(config_path, **kwargs):
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
    return ESCVR(
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

class ESCVR(Agent):
    """
       An agent that Perform Extremum Seeking
    """

    def __init__(self, db_path, file_path, curvefitfig_path,remote_input_file, default_pf, ESC_SOC_Limit,
                 inverter_rated_S, normalizing_voltage, max_iter_ESC_Vltg_Reg,
                 ESC_Step_Time, SOC_UP_VltReg_Limit, SOC_DN_VltReg_Limit, **kwargs):
        super(ESCVR, self).__init__(**kwargs)

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

        #General constants used
        self.act_reac_ratio = 0.5
        self.real_power_data = []
        self.reactive_power_data = []
        self.time_data = []
        self.registers = {}
        self.PU_Voltage= 1

        #For voltage up and down
        self.Volt_UP_Called = 0
        self.Volt_DN_Called = 0

        # Initialize all OperationalData attributes to zero
        self.allow_opr = 0
        self.fix_power_mode = 0
        self.voltage_regulation_mode = 0
        self.ESC_volt_reg_mode = 0
        self.fix_real_power = 0
        self.fix_reactive_power = 0
        self.QVVMax = 0
        self.VVVMax_Per = 0.0
        self.Low_Volt_Lmt = 0.0
        self.High_Volt_Lmt = 0.0
        self.ESC_VA = 0
        self.ESC_VA_steps = 0
        self.ESC_Repeat_Time = 0

        # Initialize all inverter data attributes to zero
        self.dc_bus_voltage = 0.0
        self.dc_bus_half_voltage = 0.0
        self.Battery_SOC = 0.0
        self.a_phase_voltage = 0.0
        self.a_phase_current = 0.0
        self.active_power = 0
        self.reactive_power = 0
        self.apparent_power = 0
        self.inverter_status = 0


        self.ESC_VOLT_REG_Runing = False
        self.real_power_data = []
        self.reactive_power_data = []
        self.time_data = []
        self.registers = {}
        self.ESC_Last_RunTime = []


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

    def fetch_selected_inverter_data(self):
        """
        Fetch only the selected inverter data (a_phase_voltage, active_power, reactive_power, apparent_power) from the DBA.
        """
        try:
            # Query to fetch the required data from the inverter_registers table
            query_selected_inverter = """
                SELECT a_phase_voltage, active_power, reactive_power, apparent_power
                FROM inverter_registers
                ORDER BY timestamp DESC
                LIMIT 1
            """
            agent_logger.info("Executing query for selected inverter data")
            self.cursor.execute(query_selected_inverter)
            selected_inverter_row = self.cursor.fetchone()

            if selected_inverter_row:
                (a_phase_voltage, active_power, reactive_power, apparent_power) = selected_inverter_row
                agent_logger.info(f"Fetched selected data from inverter_registers: {selected_inverter_row}")
                return {
                    'a_phase_voltage': a_phase_voltage,
                    'active_power': active_power,
                    'reactive_power': reactive_power,
                    'apparent_power': apparent_power
                }
            else:
                agent_logger.info("No data found in inverter_registers table for selected variables.")
                return {}

        except sqlite3.Error as e:
            agent_logger.error(f"Error fetching selected inverter data: {e}")
            return {}

    def fetch_from_DBA(self):


        # Fetch all operational and inverter register data from the DBA.
        try:
            # Query to fetch all required data from the operational_data table
            query_operational = """
                SELECT allow_opr, fix_power_mode, voltage_regulation_mode, ESC_volt_reg_mode, 
                       fix_real_power, fix_reactive_power, QVVMax, VVVMax_Per, Low_Volt_Lmt, High_Volt_Lmt, 
                       ESC_VA, ESC_VA_steps, ESC_Repeat_Time
                FROM operational_data
                ORDER BY timestamp DESC
                LIMIT 1
            """
            agent_logger.info("Executing query for operational_data")
            self.cursor.execute(query_operational)
            operational_row = self.cursor.fetchone()

            if operational_row:
                (allow_opr, fix_power_mode, voltage_regulation_mode, ESC_volt_reg_mode,
                 fix_real_power, fix_reactive_power, QVVMax, VVVMax_Per, Low_Volt_Lmt, High_Volt_Lmt,
                 ESC_VA, ESC_VA_steps, ESC_Repeat_Time) = operational_row
                agent_logger.info(f"Fetched from operational_data: {operational_row}")
            else:
                agent_logger.info("No data found in operational_data table")
                return {}

            # Query to fetch all inverter register data from the inverter_registers table
            query_inverter = """
                SELECT dc_bus_voltage, dc_bus_half_voltage, Battery_SOC, a_phase_voltage, a_phase_current, 
                       active_power, reactive_power, apparent_power, inverter_status
                FROM inverter_registers
                ORDER BY timestamp DESC
                LIMIT 1
            """
            agent_logger.info("Executing query for inverter_registers")
            self.cursor.execute(query_inverter)
            inverter_row = self.cursor.fetchone()

            if inverter_row:
                (dc_bus_voltage, dc_bus_half_voltage, Battery_SOC, a_phase_voltage, a_phase_current,
                 active_power, reactive_power, apparent_power, inverter_status) = inverter_row
                agent_logger.info(f"Fetched from inverter_registers: {inverter_row}")
            else:
                agent_logger.info("No data found in inverter_registers table")
                return {}

            # Combine the results into a dictionary and return
            return {
                'allow_opr': allow_opr,
                'fix_power_mode': fix_power_mode,
                'voltage_regulation_mode': voltage_regulation_mode,
                'ESC_volt_reg_mode': ESC_volt_reg_mode,
                'fix_real_power': fix_real_power,
                'fix_reactive_power': fix_reactive_power,
                'QVVMax': QVVMax,
                'VVVMax_Per': VVVMax_Per,
                'Low_Volt_Lmt': Low_Volt_Lmt,
                'High_Volt_Lmt': High_Volt_Lmt,
                'ESC_VA': ESC_VA,
                'ESC_VA_steps': ESC_VA_steps,
                'ESC_Repeat_Time': ESC_Repeat_Time,
                'dc_bus_voltage': dc_bus_voltage,
                'dc_bus_half_voltage': dc_bus_half_voltage,
                'Battery_SOC': Battery_SOC,
                'a_phase_voltage': a_phase_voltage,
                'a_phase_current': a_phase_current,
                'active_power': active_power,
                'reactive_power': reactive_power,
                'apparent_power': apparent_power,
                'inverter_status': inverter_status
            }

        except sqlite3.Error as e:
            agent_logger.error(f"Error fetching data: {e}")
            return {}

    #First
    def check_and_run_ESC(self):
        # Get the current time
        current_time = datetime.datetime.now()

        # Check if ESC_Last_RunTime is empty or None
        if not self.ESC_Last_RunTime:
            agent_logger.info("ESC_Last_RunTime is empty. Running ESC for the first time.")
            self.Run_ESC_For_Optimal_PQ()  # Call the function to run ESC
            self.ESC_Last_RunTime = current_time  # Update the last run time
        else:
            # Calculate the time difference in minutes
            last_run_time = self.ESC_Last_RunTime
            elapsed_time = (current_time - last_run_time).total_seconds() / 60  # Convert to minutes
            agent_logger.info(f"Last ECS run was {elapsed_time:.2f} min ago")

            if elapsed_time > 40:
                agent_logger.info(f"Last run was {elapsed_time:.2f} min ago. Running ESC again.")
                self.Run_ESC_For_Optimal_PQ()  # Call the function to run ESC
                self.ESC_Last_RunTime = current_time  # Update the last run time
            else:
                agent_logger.info(f"Last run was {elapsed_time:.2f} minutes ago. Skipping ESC run.")

    # Second
    def Run_ESC_For_Optimal_PQ(self):
        try:
            PU_Voltage = self.a_phase_voltage / self.normalizing_voltage
            agent_logger.info(f"Voltage {PU_Voltage}")
            direction = 1
            if PU_Voltage > 1:
                direction = -1  # Correct indentation and syntax
            peer = "ESCagent-0.1_1"
            agent_logger.info("RPC call for Run_E_Seeking")
            self.vip.rpc.call(peer, 'Run_E_Seeking', direction).get(timeout=600)  # Fixed case of 'direction'
        except Timeout:
            agent_logger.error("RPC call timed out after 10 minutes.")
            time.sleep(1)

    def RUN_VOLTAGE_REGULATION(self, PU_Voltage):

        self.check_and_run_ESC()
        agent_logger.warning(f"Current SOC is {self.Battery_SOC}%. Limits are {self.SOC_UP_VltReg_Limit }% and {self.SOC_DN_VltReg_Limit}%. Some Voltage correction may not run if out of range.")

        if PU_Voltage < self.Low_Volt_Lmt and self.Battery_SOC > self.SOC_UP_VltReg_Limit :
            try:
                agent_logger.info("RPC call for voltage UP")
                peer = "PQAdjagent-0.1_1"
                self.vip.rpc.call(peer, 'PQ_Volt_UP', self.Volt_UP_Called).get(timeout=600)
                # Whether to start from the same power levels or reinitialize power levels, when called again
                self.Volt_UP_Called = 1
                self.Volt_DN_Called = 0
            except Timeout:
                agent_logger.error("RPC call timed out after 10 minutes.")

                time.sleep(1)

        if PU_Voltage > self.High_Volt_Lmt and self.Battery_SOC < self.SOC_DN_VltReg_Limit:
            try:
                agent_logger.info("RPC call for voltage DOWN")
                peer = "PQAdjagent-0.1_1"
                self.vip.rpc.call(peer, 'PQ_Volt_DN',self.Volt_DN_Called).get(timeout=600)
                # Whether to start from the same power levels or reinitialize power levels, when called again
                self.Volt_UP_Called = 0
                self.Volt_DN_Called = 1
            except Timeout:
                agent_logger.error("RPC call timed out after 10 minutes.")

    @RPC.export
    def turn_off_ESC_volt_reg(self):
        agent_logger.info("ESC_volt_reg Turned off..")
        self.ESC_VOLT_REG_Runing = False

    @Core.receiver('onstop')
    def on_stop(self, sender, **kwargs):
        self.ESC_VOLT_REG_Runing= False
        agent_logger.info("ESC agent stopped.")

    @Core.receiver('onstart')
    def on_start(self, sender, **kwargs):
        """Agent startup logic."""
        agent_logger.info("ESC Agent started, waiting for 20 seconds before starting operations...")
        time.sleep(20)

        while True:

            # Fetch the register values from database
            registers = self.fetch_from_DBA()
            if registers:
                # Updated attribute assignment based on new structure
                self.allow_opr = registers.get('allow_opr')
                self.fix_power_mode = registers.get('fix_power_mode')
                self.voltage_regulation_mode = registers.get('voltage_regulation_mode')
                self.ESC_volt_reg_mode = registers.get('ESC_volt_reg_mode')
                self.fix_real_power = registers.get('fix_real_power')
                self.fix_reactive_power = registers.get('fix_reactive_power')
                self.QVVMax = registers.get('QVVMax')
                self.VVVMax_Per = registers.get('VVVMax_Per')
                self.Low_Volt_Lmt = registers.get('Low_Volt_Lmt')
                self.High_Volt_Lmt = registers.get('High_Volt_Lmt')
                self.ESC_VA = registers.get('ESC_VA')
                self.ESC_VA_steps = registers.get('ESC_VA_steps')
                self.ESC_Repeat_Time = registers.get('ESC_Repeat_Time')

                # Inverter-specific data
                self.dc_bus_voltage = registers.get('dc_bus_voltage')
                self.dc_bus_half_voltage = registers.get('dc_bus_half_voltage')
                self.Battery_SOC = registers.get('Battery_SOC')
                self.a_phase_voltage = registers.get('a_phase_voltage')
                self.a_phase_current = registers.get('a_phase_current')
                self.active_power = registers.get('active_power')
                self.reactive_power = registers.get('reactive_power')
                self.apparent_power = registers.get('apparent_power')
                self.inverter_status = registers.get('inverter_status')

                ## Log the updated operational and inverter data
            else:
                agent_logger.info("No operational or inverter data found")

            # Print Msg
            PU_Voltage = self.a_phase_voltage / self.normalizing_voltage
            agent_logger.info(f"Voltage {PU_Voltage}")

            if PU_Voltage > self.Low_Volt_Lmt and PU_Voltage < self.High_Volt_Lmt:
                agent_logger.info(f"Voltage {PU_Voltage} is already within bounds!")

            if self.ESC_volt_reg_mode and self.allow_opr and (
                    PU_Voltage < self.Low_Volt_Lmt or PU_Voltage > self.High_Volt_Lmt):

                # ************Initializing voltage regulation ****************
                if not self.ESC_VOLT_REG_Runing:
                    self.ESC_VOLT_REG_Runing = True
                    self.Volt_UP_Called=0
                    self.Volt_DN_Called=0
                    agent_logger.info("ESC_VOLT_REG_Running made true...")
                else:
                    agent_logger.info("ESC_VOLT_REG_Running already TRUE, skipping initialization.")
                # *********************************************************

                # ***********RUN ESC to find right combo of PQ ***************
                if self.ESC_VOLT_REG_Runing:
                    self.RUN_VOLTAGE_REGULATION(PU_Voltage)
                # *********************************************************

            time.sleep(5)


def main():
    """Main method called to start the agent."""
    try:
        utils.vip_main(escvr_factory, version=__version__)
    except Exception as e:
        agent_logger.exception('Unhandled exception in main')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass


