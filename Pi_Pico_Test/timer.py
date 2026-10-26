from machine import Pin
from time import sleep
from config import PicoConfig

class PicoController:
    # Main controller class for RPI Pico pin operations

    def __init__(self):
        # Initialize the controller with pins and timer
        self.config = PicoConfig()
        self._init_pins()
        self._init_timer()

    def _init_pins(self):

        #initialize LED
        self.led = Pin(
            self.config.Pins.LED,
            Pin.OUT
        )
        self.led.low() # start w LED off