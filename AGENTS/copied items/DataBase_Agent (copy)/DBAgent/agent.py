__docformat__ = 'reStructuredText'

import logging
import sys
import time
from datetime import timedelta
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.agent import utils
import os
import sqlite3


# Setup agent-specific logging
# Generalized log file path in the home folder
agent_log_file = os.path.expanduser('~/Log_Files/DataBaseAgent.log')
agent_logger = logging.getLogger('DataBaseAgent')
agent_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(agent_log_file)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
agent_logger.addHandler(file_handler)

utils.setup_logging()
__version__ = '0.1'


# Classes to represent different data sets
class LocalInputs:
    def __init__(self, fix_power_mode, voltage_regulation_mode, ESC_volt_reg_mode, fix_real_power, fix_reactive_power, QVVMax, VVVMax_Per, Low_Volt_Lmt, High_Volt_Lmt, ESC_VA, ESC_VA_steps, ESC_Repeat_Time):
        self.fix_power_mode = fix_power_mode
        self.voltage_regulation_mode = voltage_regulation_mode
        self.ESC_volt_reg_mode = ESC_volt_reg_mode
        self.fix_real_power = fix_real_power
        self.fix_reactive_power = fix_reactive_power
        self.QVVMax = QVVMax
        self.VVVMax_Per = VVVMax_Per
        self.Low_Volt_Lmt = Low_Volt_Lmt
        self.High_Volt_Lmt = High_Volt_Lmt
        self.ESC_VA = ESC_VA
        self.ESC_VA_steps = ESC_VA_steps
        self.ESC_Repeat_Time = ESC_Repeat_Time


class RemoteInputs:
    def __init__(self, fix_power_mode, voltage_regulation_mode, ESC_volt_reg_mode, fix_real_power, fix_reactive_power, QVVMax, VVVMax_Per, Low_Volt_Lmt, High_Volt_Lmt, ESC_VA, ESC_VA_steps, ESC_Repeat_Time):
        self.fix_power_mode = fix_power_mode
        self.voltage_regulation_mode = voltage_regulation_mode
        self.ESC_volt_reg_mode = ESC_volt_reg_mode
        self.fix_real_power = fix_real_power
        self.fix_reactive_power = fix_reactive_power
        self.QVVMax = QVVMax
        self.VVVMax_Per = VVVMax_Per
        self.Low_Volt_Lmt = Low_Volt_Lmt
        self.High_Volt_Lmt = High_Volt_Lmt
        self.ESC_VA = ESC_VA
        self.ESC_VA_steps = ESC_VA_steps
        self.ESC_Repeat_Time = ESC_Repeat_Time


class OperationalData:
    def __init__(self, allow_opr, fix_power_mode, voltage_regulation_mode, ESC_volt_reg_mode, fix_real_power, fix_reactive_power, QVVMax, VVVMax_Per, Low_Volt_Lmt, High_Volt_Lmt, ESC_VA, ESC_VA_steps, ESC_Repeat_Time):
        self.allow_opr = allow_opr
        self.fix_power_mode = fix_power_mode
        self.voltage_regulation_mode = voltage_regulation_mode
        self.ESC_volt_reg_mode = ESC_volt_reg_mode
        self.fix_real_power = fix_real_power
        self.fix_reactive_power = fix_reactive_power
        self.QVVMax = QVVMax
        self.VVVMax_Per = VVVMax_Per
        self.Low_Volt_Lmt = Low_Volt_Lmt
        self.High_Volt_Lmt = High_Volt_Lmt
        self.ESC_VA = ESC_VA
        self.ESC_VA_steps = ESC_VA_steps
        self.ESC_Repeat_Time = ESC_Repeat_Time


class SafetyData:
    def __init__(self, remote_comm, modbus_comm, master_switch):
        self.remote_comm = remote_comm
        self.modbus_comm = modbus_comm
        self.master_switch = master_switch


class InverterData:
    def __init__(self, timestamp, dc_bus_voltage, dc_bus_half_voltage, Battery_SOC, a_phase_voltage, a_phase_current, active_power, reactive_power, apparent_power, inverter_status):
        self.timestamp = timestamp
        self.dc_bus_voltage = dc_bus_voltage
        self.dc_bus_half_voltage = dc_bus_half_voltage
        self.Battery_SOC = Battery_SOC
        self.a_phase_voltage = a_phase_voltage
        self.a_phase_current = a_phase_current
        self.active_power = active_power
        self.reactive_power = reactive_power
        self.apparent_power = apparent_power
        self.inverter_status = inverter_status

class ESCData:
    def __init__(self, Act_Reac_Ratio):
        self.Act_Reac_Ratio = Act_Reac_Ratio



class DBAgent(Agent):
    def __init__(self, setting1=1, setting2="some/random/topic", **kwargs):
        # Initialize the agent
        kwargs.pop('config_path', None)
        super(DBAgent, self).__init__(**kwargs)
        agent_logger.info("Database agent initialization")

        self.setting1 = setting1
        self.setting2 = setting2
        self.default_config = {"setting1": setting1, "setting2": setting2}
        self.vip.config.set_default("config", self.default_config)

        # Later move to config
        self.db_path = os.path.expanduser('~/Log_Files/inverter_operations.db')  # Update path as necessary
        self.file_path = os.path.expanduser('~/Log_Files/register_data_log.txt')
        self.curvefitfig_path = os.path.expanduser(f"~/Log_Files/curvefit.png")
        self.local_file ='~/DSO_IN/LocalInputs.txt'
        self.remote_file='~/DSO_IN/RemoteInputs.txt'
        self.default_pf = 0.5
        self.ESC_SOC_Limit=25
        self.inverter_rated_S = 11000
        self.normalizing_voltage = 120
        self.max_iter_ESC_Vltg_Reg = 100
        self.ESC_Step_Time = 2
        self.SOC_UP_VltReg_Limit = 25
        self.SOC_DN_VltReg_Limit = 95

        self.database_path =  self.db_path
        self.safety_data = SafetyData(remote_comm=0, modbus_comm=0, master_switch=0)
        self.ESCData= ESCData(Act_Reac_Ratio = 0.85)


        # Initialize OperationalData with the values you provided
        self.operational_data = OperationalData(
            allow_opr=0,
            fix_power_mode=0,
            voltage_regulation_mode=0,
            ESC_volt_reg_mode=0,
            fix_real_power=5,
            fix_reactive_power=5,
            QVVMax=1000,
            VVVMax_Per=5,
            Low_Volt_Lmt=0.95,
            High_Volt_Lmt=1.05,
            ESC_VA=1200,
            ESC_VA_steps=200,
            ESC_Repeat_Time=60
        )

        self.init_database()

        # Insert a row in safety_data WITH THE DEFAULT VALUES DEFINED
        self.cursor.execute('''
            INSERT INTO safety_data (timestamp) VALUES (?)
        ''', (time.strftime('%Y-%m-%d %H:%M:%S'),))

        # Insert the initial value in the ESC_data table if the table is empty
        self.cursor.execute(
            "INSERT INTO ESC_data (Act_Reac_Ratio) SELECT 0.85 WHERE NOT EXISTS (SELECT 1 FROM ESC_data)")

        # Insert a row in operational_data with the initialized values
        self.cursor.execute('''
            INSERT INTO operational_data (
                timestamp, allow_opr, fix_power_mode, voltage_regulation_mode, ESC_volt_reg_mode, 
                fix_real_power, fix_reactive_power, QVVMax, VVVMax_Per, Low_Volt_Lmt, High_Volt_Lmt, 
                ESC_VA, ESC_VA_steps, ESC_Repeat_Time
            ) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            time.strftime('%Y-%m-%d %H:%M:%S'),  # timestamp
            self.operational_data.allow_opr,  # allow_opr
            self.operational_data.fix_power_mode,  # fix_power_mode
            self.operational_data.voltage_regulation_mode,  # voltage_regulation_mode
            self.operational_data.ESC_volt_reg_mode,  # ESC_volt_reg_mode
            self.operational_data.fix_real_power,  # fix_real_power
            self.operational_data.fix_reactive_power,  # fix_reactive_power
            self.operational_data.QVVMax,  # QVVMax
            self.operational_data.VVVMax_Per,  # VVVMax_Per
            self.operational_data.Low_Volt_Lmt,  # Low_Volt_Lmt
            self.operational_data.High_Volt_Lmt,  # High_Volt_Lmt
            self.operational_data.ESC_VA,  # ESC_VA
            self.operational_data.ESC_VA_steps,  # ESC_VA_steps
            self.operational_data.ESC_Repeat_Time  # ESC_Repeat_Time
        ))

        # Commit the changes to the database
        self.conn.commit()


    def init_database(self):
        """Initialize the SQLite database and create tables if they don't exist."""

        # Generalized database file path in the home folder
        self.conn = sqlite3.connect(self.database_path)

        self.cursor = self.conn.cursor()

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS local_inputs (
                timestamp TEXT,
                fix_power_mode INTEGER,
                voltage_regulation_mode INTEGER,
                ESC_volt_reg_mode INTEGER,
                fix_real_power INTEGER,
                fix_reactive_power INTEGER,
                QVVMax INTEGER,
                VVVMax_Per REAL,
                Low_Volt_Lmt REAL,
                High_Volt_Lmt REAL,
                ESC_VA INTEGER,
                ESC_VA_steps INTEGER,
                ESC_Repeat_Time INTEGER
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS remote_inputs (
                timestamp TEXT,
                fix_power_mode INTEGER,
                voltage_regulation_mode INTEGER,
                ESC_volt_reg_mode INTEGER,
                fix_real_power INTEGER,
                fix_reactive_power INTEGER,
                QVVMax INTEGER,
                VVVMax_Per REAL,
                Low_Volt_Lmt REAL,
                High_Volt_Lmt REAL,
                ESC_VA INTEGER,
                ESC_VA_steps INTEGER,
                ESC_Repeat_Time INTEGER
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS operational_data (
                timestamp TEXT,
                allow_opr INTEGER DEFAULT 0,
                fix_power_mode INTEGER,
                voltage_regulation_mode INTEGER,
                ESC_volt_reg_mode INTEGER,
                fix_real_power INTEGER,
                fix_reactive_power INTEGER,
                QVVMax INTEGER,
                VVVMax_Per REAL,
                Low_Volt_Lmt REAL,
                High_Volt_Lmt REAL,
                ESC_VA INTEGER,
                ESC_VA_steps INTEGER,
                ESC_Repeat_Time INTEGER
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS safety_data (
                timestamp TEXT,
                remote_comm INTEGER DEFAULT 1,
                modbus_comm INTEGER DEFAULT 0,
                master_switch INTEGER DEFAULT 1
            )
        ''')


        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS inverter_registers (
                timestamp TEXT,
                dc_bus_voltage REAL,            
                dc_bus_half_voltage REAL,       
                Battery_SOC REAL,               
                a_phase_voltage REAL,           
                a_phase_current REAL,           
                active_power REAL,              
                reactive_power REAL,            
                apparent_power REAL,            
                inverter_status INTEGER
            )
        ''')

        # Create the new ESC_data table with the Act_Reac_Ratio column
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ESC_data (
                Act_Reac_Ratio REAL DEFAULT 0.85
            )
        ''')



        self.conn.commit()
        agent_logger.info("Database initialized.")

    def insert_inverter_data(self, inverter_data):
        """Insert the inverter data into the database."""
        agent_logger.info("inside Inverter data insert.")
        timestamp = inverter_data.timestamp
        values = (timestamp, inverter_data.dc_bus_voltage, inverter_data.dc_bus_half_voltage,
                  inverter_data.Battery_SOC, inverter_data.a_phase_voltage, inverter_data.a_phase_current,
                  inverter_data.active_power, inverter_data.reactive_power, inverter_data.apparent_power,
                  inverter_data.inverter_status)

        query = '''
            INSERT INTO inverter_registers (
                timestamp, dc_bus_voltage, dc_bus_half_voltage, Battery_SOC, a_phase_voltage, a_phase_current, active_power, reactive_power, apparent_power, inverter_status
            ) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        self.cursor.execute(query, values)
        self.conn.commit()
        agent_logger.info("Inverter data inserted into the database.")

    def update_database(self, table_name, data_object):
        """Update the database with the current state."""
        agent_logger.info("Inside update database")
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

        # If data_object is a class instance, convert it to a dictionary
        if hasattr(data_object, '__dict__'):
            data = (timestamp,) + tuple(vars(data_object).values())
        elif isinstance(data_object, dict):  # If it's already a dictionary, use it as is
            data = (timestamp,) + tuple(data_object.values())
        else:
            raise TypeError("data_object must be a class instance or a dictionary")

        placeholders = ', '.join('?' * len(data))
        query = f'INSERT INTO {table_name} VALUES ({placeholders})'

        self.cursor.execute(query, data)
        self.conn.commit()
        agent_logger.info(f"Database updated with current {table_name} state.")

    def _convert_to_dict(self, data_object):
        """Convert a data object to a dictionary if it has a __dict__ attribute."""
        if hasattr(data_object, '__dict__'):
            return data_object.__dict__  # Convert object to a dictionary
        elif isinstance(data_object, dict):
            return data_object  # If already a dictionary, return it as is
        else:
            raise TypeError("Data object must be a class instance with __dict__ or a dictionary")

    def fetch_from_database(self, table_name):
        """
        Fetch the latest data from the database for the given table.
        Args:
            table_name (str): Name of the table from which to fetch data.

        Returns:
            dict: The latest data in the table as a dictionary.
        """
        agent_logger.info(f"Fetching the latest data from the database for table: {table_name}")

        if self.conn is None:
            agent_logger.error("No database connection available!")
            return {}

        try:
            # Use a column to order the rows and fetch the latest entry
            query = f"SELECT * FROM {table_name} ORDER BY timestamp DESC LIMIT 1"
            cursor = self.conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()

            if result:
                # Fetch the column names dynamically
                column_names = [description[0] for description in cursor.description]

                # Ensure the number of column names matches the number of values in the result
                if len(column_names) == len(result):
                    latest_data = dict(zip(column_names, result))  # Convert to dictionary
                    agent_logger.info(f"Latest data fetched from {table_name}: {latest_data}")
                    return latest_data
                else:
                    agent_logger.error("Mismatch between column names and row data")
                    return {}
            else:
                agent_logger.error(f"No data found in {table_name} table")
                return {}

        except Exception as e:
            agent_logger.error(f"Error fetching data from {table_name}: {e}")
            return {}

    @RPC.export
    def update_data(self, data_type, **kwargs):
        """Centralized method to handle data updates from various sources."""
        agent_logger.info(f"RPC call. Data received for update: {kwargs}")
        agent_logger.info(f"RPC call. Data type for update: {data_type}")

        if data_type == 'safety_data':
            # Fetch the current data from the database
            agent_logger.info("Safety Data fetching")
            current_data = self.fetch_from_database('safety_data')

            # Update specific fields in the safety data
            for key, value in kwargs.items():
                if hasattr(self.safety_data, key):
                    setattr(self.safety_data, key, value)
                    agent_logger.info(f"Updating key {key} with value: {value}")

            # Merge current data with updated fields to keep unchanged fields intact
            for key, value in current_data.items():
                if key not in kwargs:
                    setattr(self.safety_data, key, value)
                    agent_logger.info(f"Updating key {key} with value: {value}")

            # Remove the 'timestamp' field before updating the database
            data_to_update = self.safety_data.__dict__.copy()  # Copy the dictionary to avoid mutating the original
            if 'timestamp' in data_to_update:
                del data_to_update['timestamp']  # Remove the 'timestamp' field

            # Now you can use self.safety_data to update the database without the timestamp
            self.update_database('safety_data', data_to_update)
            agent_logger.info(f"Updated safety_data (without timestamp): {data_to_update}")
        else:
            agent_logger.error("Invalid data_type received")

    def read_files_and_update_data(self):
        """Reads LocalInputs.txt and RemoteInputs.txt, and updates the database with the values."""
        # Read and update local inputs
        agent_logger.info("Inside read files local")
        local_input_file = self.local_file

        if os.path.exists(local_input_file):
            with open(local_input_file, 'r') as file:
                lines = file.readlines()
                if len(lines) >= 12:  # Ensure there are exactly 12 lines
                    self.local_inputs = LocalInputs(
                        int(lines[0].split('=')[1].strip()),  # fix_power_mode
                        int(lines[1].split('=')[1].strip()),  # voltage_regulation_mode
                        int(lines[2].split('=')[1].strip()),  # ESC_volt_reg_mode
                        int(lines[3].split('=')[1].strip()),  # fix_real_power
                        int(lines[4].split('=')[1].strip()),  # fix_reactive_power
                        int(lines[5].split('=')[1].strip()),  # QVVMax
                        float(lines[6].split('=')[1].strip()),  # VVVMax_Per
                        float(lines[7].split('=')[1].strip()),  # Low_Volt_Lmt
                        float(lines[8].split('=')[1].strip()),  # High_Volt_Lmt
                        int(lines[9].split('=')[1].strip()),  # ESC_VA
                        int(lines[10].split('=')[1].strip()),  # ESC_VA_steps
                        int(lines[11].split('=')[1].strip())  # ESC_Repeat_Time
                    )
                    # Update the database with the new data
                    self.update_database('local_inputs', self.local_inputs)
                else:
                    agent_logger.error(f"File {local_input_file} has an incorrect format or insufficient data.")

        # Read and update remote inputs
        agent_logger.info("Inside read files remote")
        remote_input_file = self.remote_file
        if os.path.exists(remote_input_file):
            with open(remote_input_file, 'r') as file:
                lines = file.readlines()
                if len(lines) >= 12:
                    self.remote_inputs = RemoteInputs(
                        int(lines[0].split('=')[1].strip()),  # fix_power_mode
                        int(lines[1].split('=')[1].strip()),  # voltage_regulation_mode
                        int(lines[2].split('=')[1].strip()),  # ESC_volt_reg_mode
                        int(lines[3].split('=')[1].strip()),  # fix_real_power
                        int(lines[4].split('=')[1].strip()),  # fix_reactive_power
                        int(lines[5].split('=')[1].strip()),  # QVVMax
                        float(lines[6].split('=')[1].strip()),  # VVVMax_Per
                        float(lines[7].split('=')[1].strip()),  # Low_Volt_Lmt
                        float(lines[8].split('=')[1].strip()),  # High_Volt_Lmt
                        int(lines[9].split('=')[1].strip()),  # ESC_VA
                        int(lines[10].split('=')[1].strip()),  # ESC_VA_steps
                        int(lines[11].split('=')[1].strip())  # ESC_Repeat_Time
                    )
                    self.update_database('remote_inputs', self.remote_inputs)







    def read_inverter_registers_and_updata_DB(self):
        agent_logger.info("Reading inverter registers and updating database.")

        peer = "testeragent-0.1_1"  # The name of the modbus agent
        try:
            agent_logger.info(f"starting tries")
            # Read inverter register values using the RPC method like read_voltage
            dc_bus_voltage = self.read_inverter_register(peer, 33071, 1) * 0.1
            dc_bus_half_voltage = self.read_inverter_register(peer, 33072, 1) * 0.1
            a_phase_voltage = self.read_inverter_register(peer, 33073, 1) * 0.1
            a_phase_current = self.read_inverter_register(peer, 33076, 1) * 0.1

            # Read Battery SOC from register 33139
            battery_soc = self.read_inverter_register(peer, 33139, 1)

            # Manually combine two registers to read 32-bit Active, Reactive, and Apparent Power
            active_power_high = self.read_inverter_register(peer, 33079, 1)  # High 16 bits
            active_power_low = self.read_inverter_register(peer, 33080, 1)  # Low 16 bits
            active_power = (active_power_high << 16) | active_power_low  # Combine high and low to 32-bit value
            if active_power >= 0x80000000:
                active_power -= 0x100000000

            reactive_power_high = self.read_inverter_register(peer, 33081, 1)  # High 16 bits
            reactive_power_low = self.read_inverter_register(peer, 33082, 1)  # Low 16 bits
            reactive_power = (reactive_power_high << 16) | reactive_power_low  # Combine high and low to 32-bit value
            if reactive_power >= 0x80000000:
                reactive_power -= 0x100000000

            apparent_power_high = self.read_inverter_register(peer, 33083, 1)  # High 16 bits
            apparent_power_low = self.read_inverter_register(peer, 33084, 1)  # Low 16 bits
            apparent_power = (apparent_power_high << 16) | apparent_power_low  # Combine high and low to 32-bit value
            if apparent_power >= 0x80000000:
                apparent_power -= 0x100000000

            # Convert inverter status from hex to integer
            inverter_status_hex = self.read_inverter_register(peer, 33095, 1)
            inverter_status = int(inverter_status_hex)

            # Create an InverterData object with Battery_SOC
            inverter_data = InverterData(
                timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
                dc_bus_voltage=dc_bus_voltage,
                dc_bus_half_voltage=dc_bus_half_voltage,
                Battery_SOC=battery_soc,  # Add SOC here
                a_phase_voltage=a_phase_voltage,
                a_phase_current=a_phase_current,
                active_power=active_power,
                reactive_power=reactive_power,
                apparent_power=apparent_power,
                inverter_status=inverter_status  # Store as integer directly
            )

            # Insert the inverter data into the database
            self.insert_inverter_data(inverter_data)

        except Exception as e:
            agent_logger.error(f"Failed to read inverter registers or update database: {str(e)}")

    def read_inverter_register(self, peer, register_address, num_registers, function_code=4):
        """
        General method to read an inverter register using the Modbus agent (tester).
        If the read fails, return -1 and log the issue.
        """
        try:
            agent_logger.info(f"Trying to read inverter reg via RPC call at register address {register_address}")
            # Attempt the RPC call
            result = self.vip.rpc.call(peer, '_Read_Inverter', register_address, num_registers, function_code).get(
                timeout=10)

            # Check if the result is valid
            if result is None:
                agent_logger.error(f"RPC call returned None for register address {register_address}.")
                return -1  # Returning -1 to indicate a failure
            if isinstance(result, list) and len(result) > 0:
                agent_logger.info(f"Successfully read inverter reg: {result[0]}")
                return result[0]  # Return the first element from the list as the valid value
            else:
                agent_logger.error(f"Unexpected result format or empty list from RPC call: {result}")
                return -1

        except Exception as e:
            agent_logger.error(f"Error during RPC call to {peer} for register {register_address}: {str(e)}")
            return -1

    @Core.receiver('onstart')
    def on_start(self, sender, **kwargs):
        agent_logger.info("Agent established")
        while True:
            self.read_files_and_update_data()
            time.sleep(2)  # Pause for 2 seconds before the next update
            self.read_inverter_registers_and_updata_DB()
            time.sleep(2)  # Pause for 2 seconds before the next update

    @Core.receiver('onstop')
    def on_stop(self, sender, **kwargs):
        self.conn.close()
        agent_logger.info("Database connection closed.")


def main():
    """Main method called to start the agent."""
    try:
        utils.vip_main(DBAgent, version=__version__)
    except Exception as e:
        agent_logger.exception('Unhandled exception in main')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
