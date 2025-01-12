from pylibftdi import BitBangDevice
import time

# Constants for ON/OFF states
ALL_OFF = 0x00

try:
    with BitBangDevice() as device:  # Automatically open and close the device
        print("FTDI device initialized in Bit Bang mode.")

        def set_all_relays(state):
            device.port = state  # Set the state of the pins directly


        # Turn all relays OFF
        set_all_relays(ALL_OFF)
        print("All relays are OFF.")


except Exception as e:
    print(f"An error occurred: {e}")

