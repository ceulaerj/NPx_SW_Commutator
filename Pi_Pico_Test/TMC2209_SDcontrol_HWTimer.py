#-----------------------------------------------
# Raspberry pico specific function library calls
#-----------------------------------------------
from machine import Pin
from machine import Pin, PWM
from machine import Pin, UART
from machine import Timer
from time import sleep
#import gc

#------------------------------------------------------------------------
# MOTOR DRIVER TMC2209 BOARD: Pin configuration and initial value setting
#------------------------------------------------------------------------
led = Pin("LED", Pin.OUT, value=1)      # RPI pico LED (toggles per direction change
VM_EN = Pin(22, Pin.OUT, value=1)       # Main motor Voltage, initial state OFF, value: '0'=ON '1'=OFF 
VCCIO_EN = Pin(10, Pin.OUT, value=0)    # IO motor voltage, initial state OFF, value: '1'=ON '0'=OFF  
INT_STEP = Pin(20, Pin.OUT, value=0)    # Motor step pin, timer pulse, initial state '0'
step_timer = Timer()
step_state = 0
INT_DIR = Pin(21, Pin.OUT, value=0)     # Motor direction pin,  initial state '0', value: '0'=CCW '1'=CW
MS2 = Pin(18, Pin.OUT, value=0)         # Motor stepsize select pin,  initial state '0'
MS1 = Pin(16, Pin.OUT, value=0)         # Motor direction pin,  initial state '0'
ENN = Pin(17, Pin.OUT, value=1)         # Motor enable pin,  initial state OFF, value: '1'=OFF '0'=ON 

#-------------------------------------------------------------------
# BOARD INITIALISATION PARAMETERS
# Enable VM
# Enable VCCIO
# Enable motor
# Microstepping setting: "MS1..MS2"
# "00" = 1/8 step
# "10" = 1/16 step (recommended for very quiet & smooth performance)
# "01" = 1/32 step
# "11" = 1/64 step
#-------------------------------------------------------------------
# Delay definitions
gdelay = 0.5                            # global dalay 1/2 second
loopdelay = 1                           # loop dalay 1 seconds
stepdelay = 0.2                         # step delay 0.2 seconds
speed = 10000                           # frequency setting of timer

# Motor Initialisation
VM_EN.value(0)          # Enable main motor voltage
#led.toggle()
sleep(gdelay)           # Wait to settle
VCCIO_EN.value(1)       # Enable Motor VCIO
#led.toggle()
sleep(gdelay)           # Wait to settle
ENN.value(0)            # Driver Enable
MS1.value(1)            # Microstep set 1
MS2.value(0)            # Microstep set 2
#led.toggle()
sleep(gdelay)           # Wait to settle

#-----------------------------------------------
# Manual stepping using timer
# Smooth transistion
#-----------------------------------------------
# Function to create signal waveform => each rising edge = one step at fixed frequency
def step_callback(t):
    global step_state
    step_state ^= 1          # toggle 0/1
    INT_STEP.value(step_state)
# Function to periodically call step_callback function to create 
def start_steps(freq):
    step_timer.init(freq=freq * 2, mode=Timer.PERIODIC, callback=step_callback)
# Function to stop step toggle
def stop_steps():
    step_timer.deinit()
    INT_STEP.value(0)


# ---- Test loop ----

while True:
#for _ in range(10):
    #print("Forward")
    stop_steps()
    INT_DIR.value(1)
    sleep(0.1)
    start_steps(speed)   # stepfrequency = speed
    sleep(stepdelay)    # stepdelay = angle
    stop_steps()
    led.toggle()   
    sleep(loopdelay)

    #print("Reverse")
    #stop_steps
    #INT_DIR.value(0)
    #sleep(0.1)
    #start_steps(11200)
    #sleep(stepdelay)
    #stop_steps
    #led.toggle()   
    #sleep(loopdelay)

    #gc.disable          # clean memory