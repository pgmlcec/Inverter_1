import os
import time
import subprocess
import logging

# Specify the folder and log file name
LOG_FOLDER = os.path.expanduser("~/Supervisory_Logs")  # Replace with your desired folder path
LOG_FILE = os.path.join(LOG_FOLDER, "Interupt_Detection.log")  # Log file in the specified folder

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

agent_logger = setup_logging()


class FileReader:
    def __init__(self):
        self.previous_remote_modes = {
            "fix_power_mode": None,
            "voltage_regulation_mode": None,
            "ESC_volt_reg_mode": None
        }

    def handle_interrupt(self):
        """Generate a message when an interrupt is detected and process the modes."""
        agent_logger.info("Interrupt detected! Mode change identified.")
        mode_processor_path = os.path.expanduser("~/AGENTS/SUPERVISORY_FUNCTIONS/mode_processor.py")
        agent_logger.info("Running mode processor script...")
        try:
            subprocess.run(["python3", mode_processor_path], check=True)
            agent_logger.info("Mode processor script executed successfully.")
        except subprocess.CalledProcessError as e:
            agent_logger.error(f"Error occurred while running mode processor script: {e}")
            exit(1)

    def read_remote_file_and_check_modes(self):
        """Reads the remote file and checks for mode changes."""
        remote_input_file = os.path.expanduser('~/DSO_IN/RemoteInputs.txt')

        if os.path.exists(remote_input_file):
            with open(remote_input_file, 'r') as file:
                lines = file.readlines()

            if len(lines) >= 3:  # Ensure there are enough lines for the modes
                # Extract mode values
                fix_power_mode = int(lines[0].split('=')[1].strip())
                voltage_regulation_mode = int(lines[1].split('=')[1].strip())
                esc_volt_reg_mode = int(lines[2].split('=')[1].strip())

                # Check for changes in modes
                interrupt_detected = (
                    self.previous_remote_modes["fix_power_mode"] is not None and
                    self.previous_remote_modes["fix_power_mode"] != fix_power_mode
                ) or (
                    self.previous_remote_modes["voltage_regulation_mode"] is not None and
                    self.previous_remote_modes["voltage_regulation_mode"] != voltage_regulation_mode
                ) or (
                    self.previous_remote_modes["ESC_volt_reg_mode"] is not None and
                    self.previous_remote_modes["ESC_volt_reg_mode"] != esc_volt_reg_mode
                )

                # Update previous modes
                self.previous_remote_modes["fix_power_mode"] = fix_power_mode
                self.previous_remote_modes["voltage_regulation_mode"] = voltage_regulation_mode
                self.previous_remote_modes["ESC_volt_reg_mode"] = esc_volt_reg_mode

                # Handle interrupt if detected
                if interrupt_detected:
                    self.handle_interrupt()
            else:
                agent_logger.error(f"File {remote_input_file} has an incorrect format or insufficient data.")
        else:
            agent_logger.error(f"File {remote_input_file} not found.")

def main():
    file_reader = FileReader()
    agent_logger.info(f"Interupt detection file started")
    # Run the task every 30 seconds
    while True:
        file_reader.read_remote_file_and_check_modes()
        time.sleep(2)

if __name__ == "__main__":
    main()
