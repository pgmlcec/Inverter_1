#!/usr/bin/env python3
import os
import shutil
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Base folder paths
LOG_FILES_FOLDER = os.path.expanduser("~/Log_Files")
DESTINATION_FOLDER_BASE = os.path.expanduser("~/Operational_Data")

def create_or_get_destination_folder():
    """
    Create a subfolder in `~/Operational_Data` named after the current date and time.
    If the folder already exists, reuse it.
    Returns the path to the subfolder.
    """
    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M")
    destination_folder = os.path.join(DESTINATION_FOLDER_BASE, current_time)

    # Check if the base folder exists
    if not os.path.exists(DESTINATION_FOLDER_BASE):
        try:
            os.makedirs(DESTINATION_FOLDER_BASE, exist_ok=True)
            logger.info(f"Base folder created: {DESTINATION_FOLDER_BASE}")
        except Exception as e:
            logger.error(f"Failed to create base folder {DESTINATION_FOLDER_BASE}: {e}")
            raise

    # Check if the subfolder exists
    if not os.path.exists(destination_folder):
        try:
            os.makedirs(destination_folder, exist_ok=True)
            logger.info(f"Subfolder created: {destination_folder}")
        except Exception as e:
            logger.error(f"Failed to create subfolder {destination_folder}: {e}")
            raise
    else:
        logger.info(f"Subfolder already exists: {destination_folder}")

    return destination_folder

def move_folder_content(source_folder, destination_folder):
    """
    Move all files and subdirectories from the source folder to the destination folder.
    :param source_folder: Path to the source folder.
    :param destination_folder: Path to the destination folder.
    """
    if not os.path.exists(source_folder):
        logger.warning(f"Source folder does not exist: {source_folder}")
        return

    for item_name in os.listdir(source_folder):
        item_path = os.path.join(source_folder, item_name)
        try:
            shutil.move(item_path, destination_folder)
            logger.info(f"Moved: {item_name} to {destination_folder}")
        except Exception as e:
            logger.error(f"Failed to move {item_name}: {e}")

if __name__ == "__main__":
    logger.info("Starting log files reorganization...")

    # Create or get the destination folder
    destination = create_or_get_destination_folder()

    # Move content from the Log_Files folder to the destination folder
    move_folder_content(LOG_FILES_FOLDER, destination)

    logger.info("Log files reorganization completed.")


