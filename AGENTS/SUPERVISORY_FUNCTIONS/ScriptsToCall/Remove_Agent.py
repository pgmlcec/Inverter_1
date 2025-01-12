import subprocess
import logging
import os

# Specify the folder and log file name
LOG_FOLDER = os.path.expanduser("~/Supervisory_Logs")  # Replace with your desired folder path
LOG_FILE = os.path.join(LOG_FOLDER, "Remove_Agent.log")  # Log file in the specified folder

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

# Path to the VOLTTRON environment and the virtual environment activation script
VIRTUAL_ENV_PATH = os.path.expanduser("~/volttron/env/bin/activate")

def activate_environment():
    """
    Activate the virtual environment and return the shell command prefix.
    """
    if not os.path.exists(VIRTUAL_ENV_PATH):
        raise FileNotFoundError(f"Virtual environment activation script not found: {VIRTUAL_ENV_PATH}")
    
    logger.info("Activating the virtual environment...")
    # Command to source the virtual environment activation script
    return f"source {VIRTUAL_ENV_PATH} &&"

def remove_agent_by_tag(agent_tag):
    """
    Remove an agent by its tag.
    :param agent_tag: The tag of the agent to remove.
    """
    try:
        # Use `vctl` to remove the agent by tag
        command = f"{activate_environment()} vctl remove --tag {agent_tag} --force"
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True, executable="/bin/bash")

        logger.info(f"Successfully removed agent with tag: {agent_tag}")
        logger.info(f"Command output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to remove agent with tag: {agent_tag}")
        logger.error(f"Error output: {e.stderr}")
        
def activate_virtual_env():
    """Return the command to activate the VOLTTRON virtual environment."""
    expanded_virtual_env_path = os.path.expanduser(VIRTUAL_ENV_PATH)
    if not os.path.exists(expanded_virtual_env_path):
        logger.error(f"Virtual environment activation script not found: {expanded_virtual_env_path}")
        exit(1)
    return f"source {expanded_virtual_env_path} &&"
    
def run_command(command, cwd=None):
    """Run a shell command and log the output."""
    try:
        logger.info(f"Executing: {command}")
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True, executable="/bin/bash", cwd=cwd
        )
        logger.info(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {command}")
        logger.error(f"Error: {e.stderr}")
        raise

        
def is_volttron_running():
    """Check if VOLTTRON is running."""
    try:
        command = f"{activate_virtual_env()} vctl status"
        result = subprocess.run(
            command, shell=True, check=False, capture_output=True, text=True, executable="/bin/bash"
        )
        
        logger.info(f"vctl status output:\n{result.stdout}")
        
        # Adjust these keywords based on the actual output of `vctl status`
        if "RUNNING" in result.stdout.upper() or "AGENT" in result.stdout.upper():
            logger.info("VOLTTRON is running.")
            return True
        elif result.returncode == 0:
            logger.info("VOLTTRON appears to be running (exit code 0).")
            return True
        else:
            logger.info("VOLTTRON is not running.")
            return False
    except subprocess.CalledProcessError as e:
        logger.error("Failed to check VOLTTRON status.")
        logger.error(f"Error: {e.stderr}")
        return False


def start_volttron():
    """Start the VOLTTRON platform."""
    volttron_dir = os.path.expanduser("~/volttron")
    volttron_start_command = f"cd {volttron_dir} && source env/bin/activate && ./start-volttron"

    try:
        if is_volttron_running():
            logger.info("VOLTTRON is already running. Skipping start command.")
            return
        
        logger.info("Starting VOLTTRON platform...")
        run_command(volttron_start_command)
        
        # Check again to confirm VOLTTRON started
        if is_volttron_running():
            logger.info("VOLTTRON platform started successfully.")
        else:
            logger.error("Failed to start the VOLTTRON platform.")
            exit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error starting VOLTTRON: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error starting VOLTTRON: {e}")
        raise        
        
        
        
        

if __name__ == "__main__":

    start_volttron()
    # List of agent tags to remove
    agent_tags = [
        "MY_Modbus_Agent",
        "MY_DataBase_Agent",
        "MY_Ops_Agent",
        "MY_VoltReg_Agent",
        "MY_FixPQ_Agent",
        "MY_ESC_Seek_Agent",
        "MY_ESC_VoltReg",
        "MY_Curve_Fit_Agent",
        "MY_PwrCntrl_ESC_Agent",
        "MY_SSwitch_Agent"
    ]

    for agent_tag in agent_tags:
        logger.info(f"Attempting to remove agent with tag: {agent_tag}")
        remove_agent_by_tag(agent_tag)

