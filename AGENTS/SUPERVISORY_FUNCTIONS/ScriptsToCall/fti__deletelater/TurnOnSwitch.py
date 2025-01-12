from pylibftdi import BitBangDevice
import time

ALL_ON = 0x0F  # Binary 1111 (all relays ON)

try:
    with BitBangDevice() as device: 
        print("FTDI device initialized in Bit Bang mode.")

        def set_all_relays(state):

            device.port = state  # Set the state of the pins directly

        # Turn all relays ON
        set_all_relays(ALL_ON)
        print("All relays are ON.")


except Exception as e:
    print(f"An error occurred: {e}")

