import os
import subprocess
import logging

# Specify the folder and log file name
LOG_FOLDER = os.path.expanduser("~/Supervisory_Logs")  # Replace with your desired folder path
LOG_FILE = os.path.join(LOG_FOLDER, "AgentInstallation.log")  # Log file in the specified folder

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

# VOLTTRON environment paths and commands
VOLTTRON_DIR = os.path.expanduser("~/volttron")  # Expand '~' to full home directory
VIRTUAL_ENV_PATH = os.path.join(VOLTTRON_DIR, "env/bin/activate")
INSTALL_SCRIPT_PATH = os.path.join(VOLTTRON_DIR, "scripts/install-agent.py")

# Updated agents to install and their configurations
AGENT_COMMANDS = [
    {
        "path": os.path.expanduser("~/AGENTS/Modbus_Comm_Agent/"),
        "config": os.path.expanduser("~/AGENTS/config"),
        "tag": "MY_Modbus_Agent",
    },
    {
        "path": os.path.expanduser("~/AGENTS/DataBase_Agent/"),
        "config": os.path.expanduser("~/AGENTS/config"),
        "tag": "MY_DataBase_Agent",
    },
    {
        "path": os.path.expanduser("~/AGENTS/ESC_Volt_Reg_Agent/"),
        "config": os.path.expanduser("~/AGENTS/config"),
        "tag": "MY_ESC_VoltReg",
    },
    {
        "path": os.path.expanduser("~/AGENTS/Ext_Seeking_Agent/"),
        "config": os.path.expanduser("~/AGENTS/config"),
        "tag": "MY_ESC_Seek_Agent",
    },
    {
        "path": os.path.expanduser("~/AGENTS/FixPower_Agent/"),
        "config": os.path.expanduser("~/AGENTS/config"),
        "tag": "MY_FixPQ_Agent",
    },
    {
        "path": os.path.expanduser("~/AGENTS/Operational_Agent/"),
        "config": os.path.expanduser("~/AGENTS/config"),
        "tag": "MY_Ops_Agent",
    },
    {
        "path": os.path.expanduser("~/AGENTS/PowerUPDown_Agent/"),
        "config": os.path.expanduser("~/AGENTS/config"),
        "tag": "MY_PwrCntrl_ESC_Agent",
    },
    {
        "path": os.path.expanduser("~/AGENTS/PQ_CurFit_Agent/"),
        "config": os.path.expanduser("~/AGENTS/config"),
        "tag": "MY_Curve_Fit_Agent",
    },
    {
        "path": os.path.expanduser("~/AGENTS/VoltageRegulation_Agent/"),
        "config": os.path.expanduser("~/AGENTS/config"),
        "tag": "MY_VoltReg_Agent",
    },
    {
        "path": os.path.expanduser("~/AGENTS/SafetySwitch_Agent/"),
        "config": os.path.expanduser("~/AGENTS/config"),
        "tag": "MY_SSwitch_Agent",
    },
]




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



def clear_log_file():
    """Clear the contents of the log file."""
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'w') as log_file:
                log_file.truncate(0)  # Truncate the file to zero length
            print(f"Cleared content of log file: {LOG_FILE}")
            logger.info("Log file content cleared.")
        else:
            print("Log file does not exist; nothing to clear.")
            logger.info("No log file found to clear.")
    except Exception as e:
        print(f"Failed to clear log file: {e}")
        raise

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

def activate_virtual_env():
    """Return the command to activate the VOLTTRON virtual environment."""
    expanded_virtual_env_path = os.path.expanduser(VIRTUAL_ENV_PATH)
    if not os.path.exists(expanded_virtual_env_path):
        logger.error(f"Virtual environment activation script not found: {expanded_virtual_env_path}")
        exit(1)
    return f"source {expanded_virtual_env_path} &&"

def install_agents():
    """Install all agents."""
    for agent in AGENT_COMMANDS:
        path = agent["path"]
        config = agent["config"]
        tag = agent["tag"]

        logger.info(f"Installing agent: {tag}")
        logger.info(f"Resolved path: {path}")
        logger.info(f"Resolved config: {config}")

        command = (
            f"{activate_virtual_env()} python3 {INSTALL_SCRIPT_PATH} -s {path} -c {config} -t {tag}"
        )
        logger.info(f"Command: {command}")
        run_command(command, cwd=VOLTTRON_DIR)

def start_agents():
    """Start all installed agents."""
    for agent in AGENT_COMMANDS:
        tag = agent["tag"]
        command = f"{activate_virtual_env()} vctl start --tag {tag}"
        logger.info(f"Starting agent: {tag}")
        run_command(command)

def show_agent_status():
    """Show the status of all agents."""
    logger.info("Fetching agent status...")
    command = f"{activate_virtual_env()} vctl status"
    run_command(command)
    
        
if __name__ == "__main__":
    try:
        logger.info("Starting agent installation process...")
        clear_log_file()
        start_volttron()
        install_agents()  	# Install new agents
        start_agents()  	# Start installed agents
        show_agent_status()  	# Show agent status
        logger.info("Agent installation process completed successfully.")
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        
        
        
        
        

