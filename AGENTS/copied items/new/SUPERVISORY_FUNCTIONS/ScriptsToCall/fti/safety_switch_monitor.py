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

# Scripts to run
ORGANIZE_FILES_SCRIPT = os.path.expanduser('~/AGENTS/SUPERVISORY_FUNCTIONS/ScriptsToCall/Organize_files.py')
REMOVE_AGENT_SCRIPT = os.path.expanduser('~/AGENTS/SUPERVISORY_FUNCTIONS/ScriptsToCall/Remove_Agent.py')
INSTALL_AND_START_AGENTS_SCRIPT = os.path.expanduser('~/AGENTS/SUPERVISORY_FUNCTIONS/ScriptsToCall/Install_AND_START_AGENTS.py')

# Ensure the scripts exist
if not os.path.exists(ORGANIZE_FILES_SCRIPT):
    logger.error(f"Organize_files.py not found at {ORGANIZE_FILES_SCRIPT}")
    exit(1)

if not os.path.exists(REMOVE_AGENT_SCRIPT):
    logger.error(f"Remove_Agent.py not found at {REMOVE_AGENT_SCRIPT}")
    exit(1)

if not os.path.exists(INSTALL_AND_START_AGENTS_SCRIPT):
    logger.error(f"Install_AND_START_AGENTS.py not found at {INSTALL_AND_START_AGENTS_SCRIPT}")
    exit(1)

def monitor_allow_opr():
    """Continuously monitor the allow_opr variable in the operational_data table."""
    logger.info("Starting allow_opr Monitoring...")

    conn = None
    cursor = None
    previous_allow_opr = 1  # Initial assumption

    while True:
        try:
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

                # Check if allow_opr has changed from 1 to 0
                if previous_allow_opr == 1 and current_allow_opr == 0:
                    logger.warning("allow_opr changed from 1 to 0. Running necessary scripts...")

                    # Run the Remove_Agent.py script
                    logger.info(f"Sleeping for 10 seconds before running {REMOVE_AGENT_SCRIPT}")
                    time.sleep(10)
                    logger.info(f"Running script: {REMOVE_AGENT_SCRIPT}")
                    subprocess.run(["python3", REMOVE_AGENT_SCRIPT], check=True)

                    # Run the Organize_files.py script
                    logger.info(f"Sleeping for 10 seconds before running {ORGANIZE_FILES_SCRIPT}")
                    time.sleep(10)
                    logger.info(f"Running script: {ORGANIZE_FILES_SCRIPT}")
                    subprocess.run(["python3", ORGANIZE_FILES_SCRIPT], check=True)

                    # Run the Install_AND_START_AGENTS.py script
                    logger.info(f"Sleeping for 10 seconds before running {INSTALL_AND_START_AGENTS_SCRIPT}")
                    time.sleep(10)
                    logger.info(f"Running script: {INSTALL_AND_START_AGENTS_SCRIPT}")
                    subprocess.run(["python3", INSTALL_AND_START_AGENTS_SCRIPT], check=True)

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

if __name__ == "__main__":
    try:
        monitor_allow_opr()
    except KeyboardInterrupt:
        logger.info("allow_opr Monitoring stopped by user.")

