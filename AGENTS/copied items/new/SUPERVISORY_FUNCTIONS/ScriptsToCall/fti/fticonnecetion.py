from pylibftdi import BitBangDevice
import time

# Constants for ON/OFF states
ALL_ON = 0x0F  # Binary 1111 (all relays ON)
ALL_OFF = 0x00  # Binary 0000 (all relays OFF)

# Initialize and configure the device
try:
    with BitBangDevice() as device:  # Automatically open and close the device
        print("FTDI device initialized in Bit Bang mode.")

        def set_all_relays(state):
            """
            Turn all relays ON or OFF based on the state.
            :param state: 0x0F for ON, 0x00 for OFF
            """
            device.port = state  # Set the state of the pins directly

        # Turn all relays ON
        set_all_relays(ALL_ON)
        print("All relays are ON.")
        time.sleep(10)  # Wait for 10 seconds

        # Turn all relays OFF
        set_all_relays(ALL_OFF)
        print("All relays are OFF.")
        time.sleep(2)  # Wait for 2 seconds

except Exception as e:
    print(f"An error occurred: {e}")

