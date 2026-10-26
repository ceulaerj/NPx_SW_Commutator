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
INT_DIR = Pin(21, Pin.OUT, value=0)     # Motor direction pin,  initial state '0', value: '0'=CCW '1'=CW
MS2 = Pin(18, Pin.OUT, value=0)         # Motor stepsize select pin,  initial state '0'
MS1 = Pin(16, Pin.OUT, value=0)         # Motor direction pin,  initial state '0'
ENN = Pin(17, Pin.OUT, value=1)         # Motor enable pin,  initial state OFF, value: '1'=OFF '0'=ON 
gdelay = 0.5                            # global dalay 1/2 second
stepdelay = 0.2                         # step delay 0.2 seconds
loopdelay = 1                           # loop dalay 1 seconds

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
VM_EN.value(0)
#led.toggle()
sleep(gdelay)
VCCIO_EN.value(1)
#led.toggle()
sleep(gdelay)
ENN.value(0)
MS1.value(1)
MS2.value(0)
#led.toggle()
sleep(gdelay)

#-----------------------------------------------
# Stepper engine using timer
# Smooth transition
#-----------------------------------------------
step_timer = Timer()
step_state = 0
current_freq = 0

def step_callback(t):
    global step_state
    step_state ^= 1
    INT_STEP.value(step_state)

def start_steps(freq):
    global current_freq
    current_freq = freq
    step_timer.init(freq=freq * 2, mode=Timer.PERIODIC, callback=step_callback)

def stop_steps():
    global current_freq
    step_timer.deinit()
    INT_STEP.value(0)
    current_freq = 0

# ----------------------------
# Smooth acceleration
# ----------------------------
def ramp_speed(target_freq, ramp_step=100, ramp_delay=0.02):
    global current_freq

    if current_freq == 0:
        current_freq = ramp_step  # start from low speed
        start_steps(current_freq)
        sleep(ramp_delay)

    # Accelerate
    if target_freq > current_freq:
        for f in range(current_freq, target_freq, ramp_step):
            start_steps(f)
            sleep(ramp_delay)

    # Decelerate
    elif target_freq < current_freq:
        for f in range(current_freq, target_freq, -ramp_step):
            start_steps(f)
            sleep(ramp_delay)

    start_steps(target_freq)
    current_freq = target_freq


# ----------------------------
# Move with ramping
# ----------------------------
def move(direction, max_speed, run_time):
    stop_steps()
    sleep(0.2)                 # ensure clean stop

    INT_DIR.value(direction)
    sleep(0.1)                 # DIR setup time

    # ramp up
    ramp_speed(max_speed)

    # run at full speed
    sleep(run_time)

    # ramp down smoothly
    ramp_speed(200)

    stop_steps()

# ----------------------------
# Main loop
# ----------------------------
while True:

    # Forward move
    move(direction=1, max_speed=2000, run_time=2)
    led.toggle()
    sleep(1)

    # Reverse move
    move(direction=0, max_speed=2000, run_time=2)
    led.toggle()
    sleep(1)
