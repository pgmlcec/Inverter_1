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
agent_log_file = os.path.expanduser('~/Log_Files/VoltVarVoltageReg.log')
agent_logger = logging.getLogger('VRLogger')
agent_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(agent_log_file)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
agent_logger.addHandler(file_handler)

utils.setup_logging()
__version__ = '0.1'


def Volt_Var_factory(config_path, **kwargs):
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
    return Volt_Var(
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


class Volt_Var(Agent):

    def __init__(self, db_path, file_path, curvefitfig_path, remote_input_file, default_pf, ESC_SOC_Limit,
                 inverter_rated_S, normalizing_voltage, max_iter_ESC_Vltg_Reg,
                 ESC_Step_Time, SOC_UP_VltReg_Limit, SOC_DN_VltReg_Limit, **kwargs):
        super(Volt_Var, self).__init__(**kwargs)

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

#-----------------------------------------------------------------------------------------
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

        self.voltvar_running = False
        self.voltage_data = []
        self.reactive_power_data = []
        self.time_data = []

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
        Fetch all operational and inverter register data from the DBA.
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
                discharge_current = abs(current_real+1)
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
                charge_current = abs(current_real)
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
   

    def VoltVarFun(self, max_reactive_power=2):
        peer = "Mod_Commagent-0.1_1"
        agent_logger.info("VoltVar started...")

        # Calculate volt_pu based on a_phase_voltage
        volt_pu = self.a_phase_voltage / self.normalizing_voltage
                              
        low_voltage_threshold = 1 - self.VVVMax_Per/100
        high_voltage_threshold = 1 + self.VVVMax_Per/100

        max_reactive_power= self.QVVMax/1000
        slope = max_reactive_power / (low_voltage_threshold - 1)

        # Determine reactive power based on volt_pu
        if volt_pu <= low_voltage_threshold:
            reactive_power = max_reactive_power
        elif volt_pu >= high_voltage_threshold:
            reactive_power = -max_reactive_power
        else:
            reactive_power = slope * (volt_pu - 1)

        agent_logger.info(f"Voltage: {volt_pu:.2f} pu, Reactive Power: {reactive_power:.2f} kVar.")

        # Write Small real power for stable operation
        fix_real_power = -100
        voltage = self.dc_bus_half_voltage
        ExecuteReacPower= reactive_power*1000
        self.Execute_Powers(fix_real_power, ExecuteReacPower,voltage)

        #reg_reactive_power = int(reactive_power * 1000 / 10)  # Scaling the reactive power
        #try:
        #    self.vip.rpc.call(peer, '_Write_Inverter', 43133, 5, 16).get(timeout=10)
        #    self.vip.rpc.call(peer, '_Write_Inverter', 43134, reg_reactive_power, 16).get(timeout=10)
        #except Exception as e:
        #    agent_logger.error(f"Error during RPC call to {peer}: {str(e)}")

    @RPC.export
    def TurnOffVoltvar(self):
        agent_logger.info("VoltVar Turned off..")
        self.voltvar_running= False

    @Core.receiver('onstart')
    def on_start(self, sender, **kwargs):
        """Agent startup logic."""
        agent_logger.info("Agent started, waiting for 10 seconds before starting operations...")
        time.sleep(10)

        while True:
            # Fetch the register values from database
            registers = self.fetch_from_DBA()
            # Check and handle the result
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

                # Log the updated operational and inverter data
                agent_logger.info(f"Operational Data: Allow Operation = {self.allow_opr}, "
                                  f"Fix Power Mode = {self.fix_power_mode}, Voltage Regulation Mode = {self.voltage_regulation_mode}, "
                                  f"ESC Voltage Regulation Mode = {self.ESC_volt_reg_mode}, Fixed Real Power = {self.fix_real_power}, "
                                  f"Fixed Reactive Power = {self.fix_reactive_power}, QVVMax = {self.QVVMax}, VVVMax Percentage = {self.VVVMax_Per}, "
                                  f"Low Voltage Limit = {self.Low_Volt_Lmt}, High Voltage Limit = {self.High_Volt_Lmt}, ESC VA = {self.ESC_VA}, "
                                  f"ESC VA Steps = {self.ESC_VA_steps}, ESC Repeat Time = {self.ESC_Repeat_Time}")

                agent_logger.info(
                    f"Inverter Data: DC Bus Voltage = {self.dc_bus_voltage}, DC Bus Half Voltage = {self.dc_bus_half_voltage}, "
                    f"Battery SOC = {self.Battery_SOC}, A Phase Voltage = {self.a_phase_voltage}, "
                    f"A Phase Current = {self.a_phase_current}, Active Power = {self.active_power}, "
                    f"Reactive Power = {self.reactive_power}, Apparent Power = {self.apparent_power}, "
                    f"Inverter Status = {self.inverter_status}")
            else:
                agent_logger.info("No operational or inverter data found")

            if self.voltage_regulation_mode and self.allow_opr:

                # ************Initializing voltage regulation ****************
                if not self.voltvar_running:
                    self.voltvar_running= True
                    """
                            Prepare volt-var settings by writing small power values before switching to remote functionality.
                    """
                    peer = "Mod_Commagent-0.1_1"
                    agent_logger.info("Preparing VoltVar initial settings...")
                else:
                    agent_logger.info("VoltVar already running, skipping initialization.")
                # *********************************************************

                # ***********RUN VOLT-VAR ***********************************
                if self.voltvar_running:
                    agent_logger.info("Running Volt var")
                    self.VoltVarFun()
                # *********************************************************

            else:
                agent_logger.info(f"Conditions not met for VoltVar: skipping. Voltage Regulation Mode = {self.voltage_regulation_mode}, Allow Operation = {self.allow_opr}")


            time.sleep(5)


#add allow operatiob from database,self.allow_operation

    @Core.receiver('onstop')
    def on_stop(self, sender, **kwargs):
        self.voltvar_running = False
        agent_logger.info("VoltVar agent stopped.")


def main():
    """Main method called to start the agent."""
    try:
        utils.vip_main(Volt_Var_factory, version=__version__)
    except Exception as e:
        agent_logger.exception('Unhandled exception in main')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

