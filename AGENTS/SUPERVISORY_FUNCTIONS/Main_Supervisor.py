#!/usr/bin/env python3

import os
import time
import subprocess
import logging


# Specify the folder and log file name
LOG_FOLDER = os.path.expanduser("~/Supervisory_Logs")  # Replace with your desired folder path
LOG_FILE = os.path.join(LOG_FOLDER, "Main_Supervisor.log")  # Log file in the specified folder

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



# Set the VOLTTRON_HOME environment variable
os.environ["VOLTTRON_HOME"] = "/home/taha/.volttron"


# Step 1: Remove any previous agent in the system
RemoveScript_path = os.path.expanduser("~/AGENTS/SUPERVISORY_FUNCTIONS/ScriptsToCall/Remove_Agent.py")
if os.path.exists(RemoveScript_path):
    logger.info("Remove script...")
    try:
        subprocess.run(["python3", RemoveScript_path], check=True)
        logger.info("Remove agent script executed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error occurred while running Remove agent script: {e}")
        exit(1)
else:
    logger.error(f"Remove agent script not found at {RemoveScript_path}.")
    exit(1)


# Step 2: Wait 60 seconds for IOT Agents to update files
#logger.info("Waiting for 60 seconds to ensure system services are ready...")
#PullCode_path = os.path.expanduser("~/AGENTS/SUPERVISORY_FUNCTIONS/Pull_Code.py")

#if os.path.exists(PullCode_path):
#    logger.info("PullCode_path executed...")
#    try:
#        subprocess.run(["python3", PullCode_path], check=True)
#        logger.info("PullCode_path script executed successfully.")
#    except subprocess.CalledProcessError as e:
#        logger.error(f"Error occurred while running PullCode_path: {e}")
#        exit(1)
#else:
#    logger.error(f"PullCode_path script not found at {PullCode_path}.")
#    exit(1)#

#PushCode_path = os.path.expanduser("~/AGENTS/SUPERVISORY_FUNCTIONS/Push_Code.py")
    
#if os.path.exists(PushCode_path):
#    logger.info("PushCode_path executed...")
#    try:
#        subprocess.run(["python3", PushCode_path], check=True)
#        logger.info("PushCode_path script executed successfully.")
#    except subprocess.CalledProcessError as e:
#        logger.error(f"Error occurred while running PushCode_path: {e}")
#        exit(1)
#else:
#    logger.error(f"PushCode_path script not found at {PushCode_path}.")
#    exit(1)
#    
#time.sleep(5)


# Step 3: Run the mode processor to process the remote file content that is run thee agents if already on 
mode_processor_path = os.path.expanduser("~/AGENTS/SUPERVISORY_FUNCTIONS/mode_processor.py")
if os.path.exists(mode_processor_path):
    logger.info("Running mode processor script...")
    try:
        subprocess.run(["python3", mode_processor_path], check=True)
        logger.info("Mode processor script executed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error occurred while running mode processor script: {e}")
        exit(1)
else:
    logger.error(f"Mode processor script not found at {mode_processor_path}.")
    exit(1)

# Step 4: Start the interrupt detector to monitor for changes
time.sleep(5)
interrupt_detector_path = os.path.expanduser("~/AGENTS/SUPERVISORY_FUNCTIONS/Interupt_Detection.py")
if os.path.exists(interrupt_detector_path):
    logger.info("Running interrupt detection script...")
    try:
        subprocess.run(["python3", interrupt_detector_path], check=True)
        logger.info("Interrupt detection script started successfully.")
    except Exception as e:
        logger.error(f"Error occurred while starting interrupt detection script: {e}")
        exit(1)
else:
    logger.error(f"Interrupt detection script not found at {interrupt_detector_path}.")
    exit(1)
    
# Step 5: Start safety monitor switch to montor the tripping
time.sleep(5)
script_path= os.path.expanduser("~/AGENTS/SUPERVISORY_FUNCTIONS/ScriptsToCall/safety_switch_monitor.py")
if os.path.exists(script_path):
    logger.info("Running safety_switch_monitordetection script...")
    try:
        result = subprocess.run(["python3", script_path],check=True)
        logger.info(f"Script {script_name} executed successfully.")
    except Exception as e:
        logger.error(f"Error occurred while starting interrupt detection script: {e}")
        exit(1)
else:
    logger.error(f"Interrupt detection script not found at {interrupt_detector_path}.")
    exit(1)
    

    
    
