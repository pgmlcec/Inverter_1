import sqlite3
import time
import subprocess
import logging
import os

# Specify the folder and log file name
LOG_FOLDER = os.path.expanduser("~/Supervisory_Logs")  # Replace with your desired folder path
LOG_FILE = os.path.join(LOG_FOLDER, "SafetySwitchMonitor.log")  # Log file in the specified folder

# Create the folder if it doesn't exist
if not os.path.exists(LOG_FOLDER):
    os.makedirs(LOG_FOLDER)
    print(f"Created log folder: {LOG_FOLDER}")

def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    return logger

logger = setup_logging()


# Database path
DATABASE_PATH = os.path.expanduser('~/Log_Files/inverter_operations.db')  # Update path as necessary

def write_remote_file_and_set_modes_to_zero(self):
    """Sets all modes to zero while preserving other file content."""
    remote_input_file = os.path.expanduser('~/DSO_IN/RemoteInputs.txt')

    if os.path.exists(remote_input_file):
        try:
            # Read the file content
            with open(remote_input_file, 'r') as file:
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
            with open(remote_input_file, 'w') as file:
                file.writelines(lines)

            agent_logger.info(f"Successfully set all modes to zero in {remote_input_file}.")
        except IOError as e:
            agent_logger.error(f"Failed to modify file {remote_input_file}: {e}")
    else:
        agent_logger.error(f"File {remote_input_file} not found.")


def monitor_allow_opr():
    """Continuously monitor the allow_opr variable in the operational_data table."""
    logger.info("Starting allow_opr Monitoring...")

    conn = None
    cursor = None
    previous_allow_opr = 1  # Initial assumption

    while True:

        try:
            '''
            # Attempt to connect to the database if not connected
            if conn is None:
                logger.info("Attempting to connect to the database...")
                conn = sqlite3.connect(DATABASE_PATH)
                cursor = conn.cursor()
                logger.info("Connected to database successfully.")

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
                logger.info(f"Current allow_opr status: {current_allow_opr}")
            '''
                # Check if allow_opr has changed from 1 to 0
                if previous_allow_opr == 1 and current_allow_opr == 0:
                    logger.warning("allow_opr changed from 1 to 0. Running necessary scripts...")

                    # make all modes 0 in script
                    logger.info(f"write all modes 0")
                    time.sleep(2)
                    write_remote_file_and_set_modes_to_zero()
                    time.sleep(2)


                # Update the previous allow_opr status
                previous_allow_opr = current_allow_opr
                previous_allow_opr = 1
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

if __name__ == "__main__":
    try:
        monitor_allow_opr()
    except KeyboardInterrupt:
        logger.info("allow_opr Monitoring stopped by user.")

