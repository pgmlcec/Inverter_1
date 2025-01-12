__docformat__ = 'reStructuredText'

import logging
import sys
from volttron.platform.agent import utils
import sqlite3
from volttron.platform.vip.agent import Agent, Core, RPC
import os
import time
import csv


"""
Setup agent-specific logging
"""
agent_log_file = os.path.expanduser('~/Log_Files/VoltageReg.log')
agent_logger = logging.getLogger('VRLogger')
agent_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(agent_log_file)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
agent_logger.addHandler(file_handler)

utils.setup_logging()
__version__ = '0.1'


class Volt_Var(Agent):
    """
       An agent that performs asynchronous Modbus RTU communication.
       """

    def __init__(self, setting1=1, setting2="some/random/topic", **kwargs):
        # Initialize the agent
        kwargs.pop('config_path', None)
        super(Volt_Var, self).__init__(**kwargs)
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
        self.inverter_rated_S = 11000

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

    def VoltVarFun(self, max_reactive_power=2):
        peer = "testeragent-0.1_1"
        agent_logger.info("VoltVar started...")

        # Calculate volt_pu based on a_phase_voltage
        volt_pu = self.a_phase_voltage / 120

        low_voltage_threshold = 0.95
        high_voltage_threshold = 1.05
        slope = max_reactive_power / (low_voltage_threshold - 1)

        # Determine reactive power based on volt_pu
        if volt_pu <= low_voltage_threshold:
            reactive_power = max_reactive_power
        elif volt_pu >= high_voltage_threshold:
            reactive_power = -max_reactive_power
        else:
            reactive_power = slope * (volt_pu - 1)

        agent_logger.info(f"Voltage: {volt_pu:.2f} pu, Reactive Power: {reactive_power:.2f} kVar.")

        reg_reactive_power = int(reactive_power * 1000 / 10)  # Scaling the reactive power
        try:
            self.vip.rpc.call(peer, '_Write_Inverter', 43133, 5, 16).get(timeout=10)
            self.vip.rpc.call(peer, '_Write_Inverter', 43134, reg_reactive_power, 16).get(timeout=10)
        except Exception as e:
            agent_logger.error(f"Error during RPC call to {peer}: {str(e)}")

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
                    peer = "testeragent-0.1_1"
                    agent_logger.info("Preparing VoltVar initial settings...")
                else:
                    agent_logger.info("VoltVar already running, skipping initialization.")
                # *********************************************************

                # ***********RUN VOLT-VAR ***********************************
                if self.voltvar_running:
                    agent_logger.info("Running Volt var")
                    #self.VoltVarFun()
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
        utils.vip_main(Volt_Var, version=__version__)
    except Exception as e:
        agent_logger.exception('Unhandled exception in main')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass



'''
--------------------------------------------------------------------------------------------------------------------------
    def read_voltage(self, peer="testeragent-0.1_1", register_address=33073, num_registers=5, function_code=4):
        try:
            result = self.vip.rpc.call(peer, '_Read_Inverter', register_address, num_registers, function_code).get(timeout=10)
            voltage_measurement = result[0] / 1200
            return voltage_measurement
        except Exception as e:
            agent_logger.error(f"Error during RPC call to {peer}: {str(e)}")
            return None


    def VoltVar(self, max_reactive_power=2, run_time=120):
        

        start_time = time.time()
        while self.voltvar_running:
            agent_logger.info("inside voltvar")
            voltage_measurement = self.read_voltage()
            if voltage_measurement is None:
                time.sleep(2)
                continue

            self.time_data.append(time.time())
            self.voltage_data.append(voltage_measurement)

            low_voltage_threshold = 0.95
            high_voltage_threshold = 1.05
            slope = max_reactive_power / (low_voltage_threshold - 1)

            if voltage_measurement <= low_voltage_threshold:
                reactive_power = max_reactive_power
            elif voltage_measurement >= high_voltage_threshold:
                reactive_power = -max_reactive_power
            else:
                reactive_power = slope * (voltage_measurement) - slope

            self.reactive_power_data.append(reactive_power)

            agent_logger.info(f"Voltage: {voltage_measurement:.2f} pu, Reactive Power: {reactive_power:.2f} kVar.")

            reg_reactive_power = int(1*(reactive_power * 1000) / 10) #negative 1 here for negative reactive power
            write_register_address = 43134
            function_code = 16
            try:
                self.vip.rpc.call(peer, '_Write_Inverter', write_register_address, reg_reactive_power, function_code).get(timeout=10)
            except Exception as e:
                agent_logger.error(f"Error during RPC call to {peer}: {str(e)}")

            # Stop the VoltVar function after the specified run time
            if time.time() - start_time >= run_time:
                self.voltvar_running = False

            time.sleep(2)

    @RPC.export
    def start_voltvar(self):
        agent_logger.info("Called from remote - VoltVar ...")
        if not self.voltvar_running:
            self.voltvar_running = True
            #self.VoltVar()
            self.run_voltvar_scenario()
            return "VoltVar started."
        return "VoltVar is already running."

    @RPC.export
    def stop_voltvar(self):
        if self.voltvar_running:
            self.voltvar_running = False
            return "VoltVar stopped."
        return "VoltVar is not running."

    def run_voltvar_scenario(self):
        # Phase 1: Read voltage for 30 seconds without Volt-Var
        start_time = time.time()
        agent_logger.info("Reading Voltage for next 100 sec ...")
        while time.time() - start_time < 60:
            voltage_measurement = self.read_voltage()
            if voltage_measurement is not None:
                self.time_data.append(time.time())
                self.voltage_data.append(voltage_measurement)
                self.reactive_power_data.append(0)  # No reactive power injection
            time.sleep(1)

        # Phase 2a: Run Volt-Var for 2 minutes (120 seconds)
        agent_logger.info("Completed Reading Voltage")
        self.voltvar_running = True
        self.VoltVar(run_time=120)


        # Phase 2b: Write zero reactive power
        #
        peer = "testeragent-0.1_1"
        agent_logger.info("Resetting Reactive power...")
        reg_reactive_power = int(5)
        write_register_address = 43134
        agent_logger.info("inside reactive power writing")
        function_code = 16
        try:
            # Make the RPC call to write the reactive power value into register 43134
            agent_logger.info(f"request Write{int(reg_reactive_power)}  for reactive_power")
            write_success = self.vip.rpc.call(peer, '_Write_Inverter', write_register_address, reg_reactive_power,
                                              function_code).get(timeout=10)
            reacP_writen = self.vip.rpc.call(peer, '_Read_Inverter', write_register_address, 1, 3).get(
                timeout=10)
            remote_register_address = 43132
            remote_Writen = self.vip.rpc.call(peer, '_Read_Inverter', remote_register_address, 1, 3).get(
                timeout=10)
            realP_register_address = 43133
            realP_Writen = self.vip.rpc.call(peer, '_Read_Inverter', realP_register_address, 1, 3).get(
                timeout=10)
            # Log the values read from the registers
            agent_logger.info(
                f"Values in Remote register, Real Power register, and Reactive Power registers are: {remote_Writen}, {realP_Writen}, {reacP_writen}"
            )
        except Exception as e:
            agent_logger.error(f"Error during RPC call to Write zero reactive power")

        #--------------------------------------------------------------------------------------------
        try:
            self.vip.rpc.call(peer, '_Write_Inverter', 43132, 0, 16).get(timeout=10)
            agent_logger.info("Written 0 to register 43132. Waiting 10 seconds...")

        except Exception as e:
            agent_logger.error(f"Error during RPC call to {peer}: {str(e)}")
        
        #--------------------------------------------------------------------------------------------



        # Phase 3: Read voltage for 1 minute without Volt-Var
        agent_logger.info("Completed Volt-Var")
        start_time = time.time()
        while time.time() - start_time < 60:
            agent_logger.info("Without volt var started")
            voltage_measurement = self.read_voltage()
            if voltage_measurement is not None:
                self.time_data.append(time.time())
                self.voltage_data.append(voltage_measurement)
                self.reactive_power_data.append(0)  # No reactive power injection
            time.sleep(2)

        self.generate_graph()

    def generate_graph(self):
        plt.figure(figsize=(10, 6))
        plt.subplot(2, 1, 1)
        plt.plot(self.time_data, self.voltage_data, label='Voltage (pu)')
        plt.xlabel('Time (s)')
        plt.ylabel('Voltage (pu)')
        plt.title('Voltage Over Time')
        plt.legend()

        plt.subplot(2, 1, 2)
        plt.plot(self.time_data, self.reactive_power_data, label='Reactive Power (kVar)', color='red')
        plt.xlabel('Time (s)')
        plt.ylabel('Reactive Power (kVar)')
        plt.title('Reactive Power Over Time')
        plt.legend()

        plt.tight_layout()
        plt.savefig('/home/taha/voltvar_results.png')
        plt.show()

        # Save data to a CSV file
        data_file = '/home/taha/voltvar_data.csv'
        with open(data_file, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Time (s)', 'Voltage (pu)', 'Reactive Power (kVar)'])
            for t, v, rp in zip(self.time_data, self.voltage_data, self.reactive_power_data):
                writer.writerow([t, v, rp])

    @Core.receiver('onstart')
    def on_start(self, sender, **kwargs):
        agent_logger.info("Agent established")



def main():
    """Main method called to start the agent."""
    try:
        utils.vip_main(Volt_Var, version=__version__)  # Changed 'Tester' to 'Validater'
    except Exception as e:
        agent_logger.exception('Unhandled exception in main')

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass





    @Core.receiver('onstart')
    def on_start(self, sender, **kwargs):
        agent_logger.info("Agent started")
        while True:
            voltage_regulation_mode, allow_operation, no_mode_running = self.read_inverter_registers_from_db()

            if voltage_regulation_mode and allow_operation:
                if no_mode_running:
                    self.voltvar_running = True
                    self.VoltVar()
                else:
                    agent_logger.info("VoltVar already running, skipping initialization.")
            else:
                agent_logger.info("Conditions not met for VoltVar: skipping.")

            time.sleep(2)
'''
