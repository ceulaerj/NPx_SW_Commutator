# Complete project details at https://RandomNerdTutorials.com/raspberry-pi-pico-pwm-micropython/
from machine import Pin, PWM
from machine import Pin
from time import sleep

# Set up PWM Pin
Pulse = Pin(16)
Enable = Pin(17, Pin.OUT)
Pulse_pwm = PWM(Pulse)
duty_step = 129  # Step size for changing the duty cycle
Enable_on = Enable.value(1)

#Set PWM frequency
frequency = 5000
Pulse_pwm.freq (frequency)

try:
    while True:
      # Increase the duty cycle gradually
      for duty_cycle in range(0, 65536, duty_step):
        Pulse_pwm.duty_u16(duty_cycle)
        Enable.toggle()
        sleep(0.005)
        
      # Decrease the duty cycle gradually
      for duty_cycle in range(65536, 0, -duty_step):
        Pulse_pwm.duty_u16(duty_cycle)
        Enable.toggle()
        sleep(0.005)
        
except KeyboardInterrupt:
    print("Keyboard interrupt")
    Pulse_pwm.duty_u16(0)
    print(Pulse_pwm)
    Pulse_pwm.deinit()