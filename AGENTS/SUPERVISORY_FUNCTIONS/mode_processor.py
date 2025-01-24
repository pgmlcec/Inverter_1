import time
import os
import subprocess
import logging

# Specify the folder and log file name
LOG_FOLDER = os.path.expanduser("~/Supervisory_Logs")  # Replace with your desired folder path
LOG_FILE = os.path.join(LOG_FOLDER, "modeprocessor.log")  # Log file in the specified folder

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


# Directory containing the scripts
SCRIPTS_DIR = os.path.expanduser('~/AGENTS/SUPERVISORY_FUNCTIONS/ScriptsToCall')

def run_script(script_name):
    """Run a Python script from the specified directory and display output in the console."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if os.path.exists(script_path):
        try:
            # Run the script and capture real-time output
            result = subprocess.run(
                ["python3", script_path],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(result.stdout)
            logger.info(f"Script {script_name} executed successfully.")
        except subprocess.CalledProcessError as e:
            print(e.stderr)
            logger.error(f"Error occurred while executing {script_name}: {e.stderr}")
    else:
        logger.error(f"Script {script_name} not found at {script_path}.")

def turn_on_switch():
    logger.info("Turn_On_Switch called.")
    run_script("TurnOnSwitch.py")
    
def turn_off_switch():
    logger.info("Turn_On_Switch called.")
    run_script("TurnOffSwitch.py")                

def install_agents():
    logger.info("Install_Agents called.")
    run_script("Install_AND_START_AGENTS.py")
    time.sleep(10)

def check_for_tripping():
    logger.info("Check for Tripping called.")
    # Simulate checking for tripping
    time.sleep(1)

def remove_agents():
    logger.info("Remove_Agents called.")
    run_script("Remove_Agent.py")

def organize_files():
    logger.info("Organize_Files called.")
    run_script("Organize_files.py")

def process_modes():
    """
    Reads the RemoteInputs.txt file and processes the modes.
    Executes appropriate functions based on mode values.
    """
    remote_input_file = os.path.expanduser('~/DSO_IN/RemoteInputs.txt')

    if os.path.exists(remote_input_file):
        with open(remote_input_file, 'r') as file:
            lines = file.readlines()

        if len(lines) >= 3:  # Ensure there are enough lines for the modes
            # Extract mode values
            fix_power_mode = int(lines[0].split('=')[1].strip())
            voltage_regulation_mode = int(lines[1].split('=')[1].strip())
            esc_volt_reg_mode = int(lines[2].split('=')[1].strip())

            # Check if any mode is 1
            if fix_power_mode == 1 or voltage_regulation_mode == 1 or esc_volt_reg_mode == 1:
                logger.info("At least one mode is ON. Executing actions...")
                turn_on_switch()
                install_agents()
                check_for_tripping()
            else:
                logger.info("All modes are OFF. Executing cleanup...")
                remove_agents()
                organize_files()
                turn_off_switch()
                
        else:
            logger.error(f"File {remote_input_file} has an incorrect format or insufficient data.")
    else:
        logger.error(f"File {remote_input_file} not found.")

if __name__ == "__main__":
    process_modes()

