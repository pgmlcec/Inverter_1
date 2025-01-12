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


"""
Setup agent-specific logging
"""
agent_log_file = os.path.expanduser('~/Log_Files/FixPQ.log')
agent_logger = logging.getLogger('FixPQLogger')
agent_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(agent_log_file)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
agent_logger.addHandler(file_handler)

utils.setup_logging()
__version__ = '0.1'


class FixPQ(Agent):
    """
       An agent that performs asynchronous Modbus RTU communication.
       """

    def __init__(self, setting1=1, setting2="some/random/topic", **kwargs):
        # Initialize the agent
        kwargs.pop('config_path', None)
        super(FixPQ, self).__init__(**kwargs)
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

        # General constants used
        self.act_reac_ratio = 0.5
        self.real_power_data = []
        self.reactive_power_data = []
        self.time_data = []
        self.registers = {}
        self.PU_Voltage = 1


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


        self.FixPQ_running = False
        self.real_power_data = []
        self.reactive_power_data = []
        self.time_data = []
        self.act_reac_ratio = 0.5

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

    def fetch_from_DBA(self):
        """
        Fetch all operational and inverter register data from the DBA and update instance variables.
        """
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
                (self.allow_opr, self.fix_power_mode, self.voltage_regulation_mode, self.ESC_volt_reg_mode,
                 self.fix_real_power, self.fix_reactive_power, self.QVVMax, self.VVVMax_Per, self.Low_Volt_Lmt,
                 self.High_Volt_Lmt, self.ESC_VA, self.ESC_VA_steps, self.ESC_Repeat_Time) = operational_row
                agent_logger.info(f"Fetched and updated operational data: {operational_row}")
            else:
                agent_logger.info("No data found in operational_data table")

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
                (self.dc_bus_voltage, self.dc_bus_half_voltage, self.Battery_SOC, self.a_phase_voltage,
                 self.a_phase_current, self.active_power, self.reactive_power, self.apparent_power,
                 self.inverter_status) = inverter_row
                agent_logger.info(f"Fetched and updated inverter data: {inverter_row}")
            else:
                agent_logger.info("No data found in inverter_registers table")

        except sqlite3.Error as e:
            agent_logger.error(f"Error fetching data: {e}")
        # ______________________________________________________________________________________________________________________
        try:
            # Corrected query to fetch active-reactive power ratio from the ESC_data table
            query_esc_data = """
                SELECT Act_Reac_Ratio
                FROM ESC_data
                LIMIT 1
            """
            agent_logger.info("Executing query for ESC_data")
            self.cursor.execute(query_esc_data)
            esc_data_row = self.cursor.fetchone()

            if esc_data_row:
                (self.act_reac_ratio,) = esc_data_row
                agent_logger.info(f"Fetched and updated ESC data: Act_Reac_Ratio = {self.act_reac_ratio}")
            else:
                self.act_reac_ratio = None
                agent_logger.info("No data found in ESC_data table")

        except sqlite3.Error as e:
            agent_logger.error(f"Error fetching data: {e}")

        # Convert Voltage to Pu
        self.PU_Voltage = self.a_phase_voltage / self.normalizing_voltage
        agent_logger.info(f"Voltage {self.PU_Voltage}")

    #Second
    def Execute_Powers(self, real_power, reactive_power, dc_bus_voltage):

        peer = "Mod_Commagent-0.1_1"

        # Calculate reactive power as a percentage of the inverter's rated capacity
        reactive_power_percentage = (reactive_power / self.inverter_rated_S) * 100

        # Check if reactive power exceeds 59% and set it to zero if it does
        if reactive_power_percentage > 59:
            agent_logger.info("Reactive power exceeds 59% of the rated capacity. Setting reactive power to 0.")
            reactive_power = 0
            reactive_power_percentage = 0
        else:
            agent_logger.info(f"Reactive Power is {reactive_power_percentage} % of the rated capacity.")

        # Scale the reactive power value for writing (according to your table: 0.01% for actual 1%)
        reg_limit_reactive_power = int(reactive_power_percentage * 100)

        # Check if the combined power exceeds the rated capacity
        combined_power = (real_power ** 2 + reactive_power ** 2) ** 0.5
        if combined_power > self.inverter_rated_S:
            agent_logger.info("Combined power exceeds the rated capacity. Setting both real and reactive power to 0.")
            real_power = 100
            reactive_power = 100
            reg_limit_reactive_power = 100  # Set reactive power register limit to zero as well

        # Calculate the current required for the real power using the DC bus voltage
        if dc_bus_voltage > 0:  # Prevent division by zero
            current_real = real_power / dc_bus_voltage
            agent_logger.info(f"Current required for Real Power: {current_real} A")
        else:
            agent_logger.error("DC Bus Voltage is zero or negative. Cannot calculate current.")
            return


        # Set the working mode to Reactive Power Mode (4)
        working_mode_reactive_power = 4

        try:
            # Step 1: Set the working mode to "Reactive Power"
            agent_logger.info("Setting working mode to Reactive Power Mode (4)")
            self.vip.rpc.call(peer, '_Write_Inverter', 43050, working_mode_reactive_power, 16).get(timeout=10)
            agent_logger.info("Working mode set to Reactive Power Mode (4)")

            # Step 2: Write the limited reactive power value to the inverter register
            agent_logger.info(f"Writing {reg_limit_reactive_power} to Limit Reactive Power register 43051")
            self.vip.rpc.call(peer, '_Write_Inverter', 43051, reg_limit_reactive_power, 16).get(timeout=10)

            # Step 3: Set charging or discharging current based on real power
            if real_power > 0:

                # Set discharge time for the entire day (start at 00:01 and end at 23:58)
                agent_logger.info("Setting discharge time for the entire day.")
                self.vip.rpc.call(peer, '_Write_Inverter', 43147, 0, 16).get(timeout=10)  # Discharge start hour to 0
                self.vip.rpc.call(peer, '_Write_Inverter', 43148, 1, 16).get(timeout=10)  # Discharge start minute to 1
                self.vip.rpc.call(peer, '_Write_Inverter', 43149, 23, 16).get(timeout=10)  # Discharge end hour to 23
                self.vip.rpc.call(peer, '_Write_Inverter', 43150, 58, 16).get(timeout=10)  # Discharge end minute to 58
                agent_logger.info("Discharge time set to 00:01 - 23:58.")

                # Set charge time for 1 minute
                agent_logger.info("Setting charge time for 1 minute")
                self.vip.rpc.call(peer, '_Write_Inverter', 43143, 23, 16).get(timeout=10)  # Charge start hour to 23
                self.vip.rpc.call(peer, '_Write_Inverter', 43144, 59, 16).get(timeout=10)  # Charge start minute to 59
                self.vip.rpc.call(peer, '_Write_Inverter', 43145, 0, 16).get(timeout=10)  # Charge end hour to 0
                self.vip.rpc.call(peer, '_Write_Inverter', 43146, 0, 16).get(timeout=10)  # Charge end minute to 0
                agent_logger.info("Charge time set to 23:59 - 00:00.")


                # Discharge the battery
                discharge_current = abs(current_real + 1)
                reg_discharge_current = int(discharge_current * 10)  # Convert to 0.1A steps
                agent_logger.info(f"Writing discharge current {reg_discharge_current} to register 43142")
                self.vip.rpc.call(peer, '_Write_Inverter', 43142, reg_discharge_current, 16).get(timeout=10)

                agent_logger.info(f"Writing charge current 0 to register 43141")
                self.vip.rpc.call(peer, '_Write_Inverter', 43141, 0, 16).get(timeout=10)


            elif real_power < 0:

                # Set charge time for the entire day (start at 00:01 and end at 23:58)
                agent_logger.info("Setting charge time for the entire day.")
                self.vip.rpc.call(peer, '_Write_Inverter', 43143, 0, 16).get(timeout=10)
                self.vip.rpc.call(peer, '_Write_Inverter', 43144, 1, 16).get(timeout=10)
                self.vip.rpc.call(peer, '_Write_Inverter', 43145, 23, 16).get(timeout=10)
                self.vip.rpc.call(peer, '_Write_Inverter', 43146, 58, 16).get(timeout=10)
                agent_logger.info("Charge time set to 00:01 - 23:58.")

                # Set discharge time for 1 minute
                agent_logger.info("Setting discharge time for 1 minute")
                self.vip.rpc.call(peer, '_Write_Inverter', 43147, 23, 16).get(timeout=10)  # Discharge start hour to 23
                self.vip.rpc.call(peer, '_Write_Inverter', 43148, 59, 16).get(timeout=10)  # Discharge start minute to 59
                self.vip.rpc.call(peer, '_Write_Inverter', 43149, 0, 16).get(timeout=10)  # Discharge end hour to 0
                self.vip.rpc.call(peer, '_Write_Inverter', 43150, 0, 16).get(timeout=10)  # Discharge end minute to 0
                agent_logger.info("Discharge time set to 23:59 - 00:00.")

                # Charge the battery
                charge_current = abs(current_real - 1)
                reg_charge_current = int(charge_current * 10)  # Convert to 0.1A steps
                agent_logger.info(f"Writing charge current {reg_charge_current} to register 43141")
                self.vip.rpc.call(peer, '_Write_Inverter', 43141, reg_charge_current, 16).get(timeout=10)

                agent_logger.info(f"Writing discharge current 0 to register 43142")
                self.vip.rpc.call(peer, '_Write_Inverter', 43142, 0, 16).get(timeout=10)


            else:
                agent_logger.info("Real power is zero, both charge discharge setting zero")
                discharge_current = 0
                reg_0_current = int(discharge_current * 10)  # Convert to 0.1A steps
                agent_logger.info(f"Writing discharge current {reg_0_current} to register 43142")
                self.vip.rpc.call(peer, '_Write_Inverter', 43142, reg_0_current, 16).get(timeout=10)
                self.vip.rpc.call(peer, '_Write_Inverter', 43141, reg_0_current, 16).get(timeout=10)

        except Exception as e:
            agent_logger.error(f"Error during RPC call to {peer}: {str(e)}")

    def FixPQFun(self):
        peer = "Mod_Commagent-0.1_1"
        agent_logger.info("Fix Power Mode started...")

        # Get fix real and reactive power from the registers
        fix_real_power = self.fix_real_power
        fix_reactive_power = self.fix_reactive_power
        voltage = self.dc_bus_half_voltage
        #voltage = self.a_phase_voltage * 2

        # Log the real and reactive power values
        agent_logger.info(
            f"Setting Fix Power Mode with Real Power: {fix_real_power} W and Reactive Power: {fix_reactive_power} Var.")

        self.Execute_Powers(fix_real_power,fix_reactive_power,voltage)


    @RPC.export
    def turn_off_fix_power(self):
        agent_logger.info("FP Turned off..")
        self.FixPQ_running= False

    @Core.receiver('onstart')
    def on_start(self, sender, **kwargs):
        """Agent startup logic."""
        agent_logger.info("Fix PQ Agent started, waiting for 10 seconds before starting operations...")
        time.sleep(10)

        while True:
            self.fetch_from_DBA()

            if self.fix_power_mode and self.allow_opr:

                # ************Initializing voltage regulation ****************
                if not self.FixPQ_running:
                    self.FixPQ_running= True
                    """
                            Prepare fix power  settings by writing small power values before switching to remote functionality.
                    """
                    peer = "Mod_Commagent-0.1_1"
                    agent_logger.info("Preparing FP mode initial settings...")

                else:
                    agent_logger.info("FixPQ already running, skipping initialization.")
                # *********************************************************


                # ***********RUN FixPQ ***********************************
                if self.FixPQ_running:
                    agent_logger.info("Running FixPQ")
                    self.FixPQFun()
                # *********************************************************

            else:
                agent_logger.info(f"Conditions not met for FixPQ: skipping. Fix power Mode = {self.fix_power_mode}, Allow Operation = {self.allow_opr}")


            time.sleep(5)


#add allow operation from database,self.allow_operation

    @Core.receiver('onstop')
    def on_stop(self, sender, **kwargs):
        self.FixPQ_running= False
        agent_logger.info("Fix power agent stopped.")


def main():
    """Main method called to start the agent."""
    try:
        utils.vip_main(FixPQ, version=__version__)
    except Exception as e:
        agent_logger.exception('Unhandled exception in main')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass


