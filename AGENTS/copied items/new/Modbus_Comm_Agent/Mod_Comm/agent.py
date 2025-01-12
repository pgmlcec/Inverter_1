"""
Asynchronous Modbus communication agent for VOLTTRON.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
import asyncio
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.agent import utils
import minimalmodbus
import threading
import time
import os


"""
Setup agent-specific logging
"""
agent_log_file = os.path.expanduser('~/Log_Files/ModbusLogger.log')
agent_logger = logging.getLogger('ModbusCommunication')
agent_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(agent_log_file)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
agent_logger.addHandler(file_handler)

utils.setup_logging()
__version__ = '0.1'

class SafetyData:
    def __init__(self, remote_comm, modbus_comm, master_switch):
        self.remote_comm = remote_comm
        self.modbus_comm = modbus_comm
        self.master_switch = master_switch


class Mod_Comm(Agent):
    """
    An agent that performs asynchronous Modbus RTU communication.
    """

    def __init__(self, setting1=1, setting2="some/random/topic", **kwargs):
        # Initialize the agent
        kwargs.pop('config_path', None)
        super(Mod_Comm, self).__init__(**kwargs)
        agent_logger.info("Mod_Comm agent initialization")
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


        # Initialize SafetyData with default values
        self.safety_data = SafetyData(remote_comm=1, modbus_comm=0, master_switch=1)


    def update_database(self, table_name, data):
        """
        Update the database using the data (dictionary of key-value pairs).
        """
        # Log the data that is being passed
        agent_logger.info(f"Updating database with data: {data}")



        if isinstance(data, dict):
            # Proceed with the RPC call if data is a dictionary
            try:
                response = self.vip.rpc.call(
                    'DBAgentagent-0.1_1',  # The name of the target agent
                    'update_data',  # The RPC method to call in that agent
                    table_name,  # The table name where data should be updated
                    **data  # Unpack the dictionary into keyword arguments
                ).get(timeout=10)  # Optional timeout
                agent_logger.info(f"Database updated successfully: {response}")
                return response
            except Exception as e:
                agent_logger.error(f"Error while updating database: {e}")
                return None
        else:
            agent_logger.error(f"Invalid data type passed: {type(data)}. Expected a dictionary.")
            raise TypeError("Data must be a dictionary")

    @RPC.export
    def _Read_Inverter(self, register_address, num_registers, function_code):
        agent_logger.info("inside mod fun")
        max_retries = 5 # Maximum number of retries
        retry_delay = 2  # Delay between retries in seconds
        topic = "error/inverter_communication"  # Define the topic where the message will be published

        try:
            agent_logger.info("connecting...")
            instrument = minimalmodbus.Instrument('/dev/Modbus_Converter', 1)
            instrument.serial.baudrate = 9600
            instrument.serial.bytesize = 8
            instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
            instrument.serial.stopbits = 1
            instrument.serial.timeout = 1

            for attempt in range(max_retries):
                # Attempt to read the registers using the provided function code
                try:
                    response = instrument.read_registers(register_address, num_registers, functioncode=function_code)
                    if response is not None:
                        agent_logger.info(f"Published input register values: {response}")

                        # Only update the database if modbus_comm has changed
                        if self.safety_data.modbus_comm != 1:
                            self.safety_data.modbus_comm = 1
                            self.update_database('safety_data', {'modbus_comm': 1})  # Update modbus_comm to 1

                        return response
                    else:
                        agent_logger.warning(f"Read attempt {attempt + 1} returned None, retrying...")
                        time.sleep(retry_delay)
                except Exception as e:
                    agent_logger.error(f"An error occurred while reading on attempt {attempt + 1}: {str(e)}")
                    time.sleep(retry_delay)

            # After all retries, log that communication was unsuccessful and publish a message
            agent_logger.error("Modbus communication failed after retries")
            # Update database with modbus_comm set to 0 (communication failed)
            self.update_database('safety_data', {'modbus_comm': 0})
            response = [-11]
            agent_logger.error(f"Returning response: {response}")
            return response  # Return None if all retries failed

        except Exception as e:
            agent_logger.error(f"An error occurred while setting up Modbus connection: {str(e)}")
            # Update database with modbus_comm set to 0 (communication failed)
            self.update_database('safety_data', {'modbus_comm': 0})
        response = [-1]
        agent_logger.error(f"Returning response: {response}")
        return response  # Return None if all retries failed

    def to_unsigned(self, value):
        """ Convert a signed integer to an unsigned integer using two's complement for 16-bit numbers. """
        if value < 0:
            return 65536 + value  # Convert negative to two's complement unsigned equivalent
        return value

    @RPC.export
    def _Write_Inverter(self, register_address, value_to_write, function_code=16):
        # Set up the serial connection parameters
        instrument = minimalmodbus.Instrument('/dev/Modbus_Converter', 1)  # Port name, slave address (in decimal)
        instrument.serial.baudrate = 9600
        instrument.serial.bytesize = 8
        instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
        instrument.serial.stopbits = 1
        instrument.serial.timeout = 1 # Timeout in seconds

        max_retries = 5000
        retry_delay = 4  # Delay between retries in seconds
        value_to_write = self.to_unsigned(value_to_write)  # Convert to unsigned if necessary


        for attempt in range(max_retries):
            try:
                # Write to the register using the provided function code
                instrument.write_register(register_address, value_to_write, functioncode=function_code)
                agent_logger.info(f"Successfully wrote {value_to_write} to register {register_address}")
                return True  # Return True to indicate success
            except minimalmodbus.NoResponseError:
                agent_logger.info(f"No response from device on attempt {attempt + 1}, retrying after {retry_delay} seconds...")
                time.sleep(retry_delay)
            except minimalmodbus.ModbusException as e:
                agent_logger.info(f"Modbus error on attempt {attempt + 1}: {str(e)}, retrying after {retry_delay} seconds...")
                time.sleep(retry_delay)
            except Exception as e:
                agent_logger.info(f"An unexpected error occurred on attempt {attempt + 1}: {str(e)}, retrying after {retry_delay} seconds...")
                time.sleep(retry_delay)

        agent_logger.info("Failed to write to register after maximum retries")
        return False  # Return False to indicate failure

    @Core.receiver('onstart')
    def on_start(self, sender, **kwargs):
        agent_logger.info("Agent stablished")

def main():
    """Main method called to start the agent."""
    try:
        utils.vip_main(Mod_Comm, version=__version__)
    except Exception as e:
        agent_logger.exception('Unhandled exception in main')

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass



