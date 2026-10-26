# Raspberry pico specific function library calls
from machine import Pin
from machine import Pin, PWM
from time import sleep

# Pin configuration and initial value setting
led = Pin("LED", Pin.OUT, value=0) # RPI pico LED (toggles per direction change
pulse = Pin(19, Pin.OUT, value=0) # connected to motor pulse input
dir = Pin(20, Pin.OUT, value=0) # connected to motor direction input

# Small test program controlling exact pulse timing for motor tuning

for i in range (2000): # number of repeating pulse train cycles, every cycle direction is changed
    
    sleep(2)
    # CALCULATION 1 REVOLUTION
    # Motor = 1,8deg/step - 200 steps per rev pulses w timing according to sleep (ms)
    # Gear ration = 15 rev motor per 47 rev RF joint
    # Microstep ratio = 200 full steps x M = setting DT320, for example: 4000 microsteps = 20 x 200 steps per rev
    # value r = microstep setting 4000, gear ratio 47/15, 1,8deg per step = 20 x 200 x 47/15 = 12533 (rounded)
    # CALCULATION RPM
    # 1 step (pulse) = 4 (t) ms period so 1 revolution (Rt) = 12533 (r) x 4(t) ms = 50132 ms
    # RPM = Rt /(60*1000) = 0,8355 RPM
    #
    for i in range(125): 
    #for i in range(131072): 
        pulse.value(1)
        #sleep(0.0001)
        sleep(0.01)
        pulse.value(0)
        #sleep(0.0001)
        sleep(0.0001)
    
    sleep(0.01)
    #dir.toggle()
    led.toggle()
