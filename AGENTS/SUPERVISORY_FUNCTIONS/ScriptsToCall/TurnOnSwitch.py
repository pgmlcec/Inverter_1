import RPi.GPIO as GPIO
import time

# Pin configuration
RELAY_PIN1 = 6  # Replace with the GPIO pin you're using
RELAY_PIN2 = 13  # Replace with the GPIO pin you're using
RELAY_PIN3 = 19  # Replace with the GPIO pin you're using
RELAY_PIN4 = 26  # Replace with the GPIO pin you're using

# GPIO setup
GPIO.setmode(GPIO.BCM)  # Use Broadcom pin numbering
GPIO.setup(RELAY_PIN1, GPIO.OUT)
GPIO.setup(RELAY_PIN2, GPIO.OUT)
GPIO.setup(RELAY_PIN3, GPIO.OUT)
GPIO.setup(RELAY_PIN4, GPIO.OUT)

try:
    print("Turning Relay GND")
    GPIO.output(RELAY_PIN1, GPIO.LOW)
    GPIO.output(RELAY_PIN2, GPIO.LOW)
    GPIO.output(RELAY_PIN3, GPIO.LOW)
    GPIO.output(RELAY_PIN4, GPIO.LOW)
    time.sleep(2)  # Wait for 2 seconds

except KeyboardInterrupt:
    print("Exiting program")

finally:
    GPIO.cleanup()  # Ensure GPIO pins are properly released