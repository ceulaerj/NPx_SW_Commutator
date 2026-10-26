#-----------------------------------------------
# Raspberry pico specific function library calls
#-----------------------------------------------
from machine import Pin
from machine import Pin, PWM
from machine import Pin, UART
from time import sleep
#import gc

#------------------------------------------------------------------------
# MOTOR DRIVER TMC2209 BOARD: Pin configuration and initial value setting
#------------------------------------------------------------------------
led = Pin("LED", Pin.OUT, value=1)      # RPI pico LED (toggles per direction change
VM_EN = Pin(22, Pin.OUT, value=1)       # Main motor Voltage, initial state OFF, value: '0'=ON '1'=OFF 
VCCIO_EN = Pin(10, Pin.OUT, value=0)   # IO motor voltage, initial state OFF, value: '1'=ON '0'=OFF  
INT_STEP = PWM(Pin(20))                 # Motor step pin,  PWM signal, 1000 steps/sec, start disabled
INT_STEP.freq(1000)                      
INT_STEP.duty_u16(0)                    
INT_DIR = Pin(21, Pin.OUT, value=0)     # Motor direction pin,  initial state '0', value: '0'=CCW '1'=CW
MS2 = Pin(18, Pin.OUT, value=0)         # Motor stepsize select pin,  initial state '0'
MS1 = Pin(16, Pin.OUT, value=0)         # Motor direction pin,  initial state '0'
ENN = Pin(17, Pin.OUT, value=1)         # Motor enable pin,  initial state OFF, value: '1'=OFF '0'=ON 
gdelay = 0.5                            # global dalay 1/2 second
stepdelay = 2                           # step delay 2 seconds
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
# Frequency = step rate (steps/sec)
# Duty cycle = 50% per pulse
# Adjust speed via freq()
# Continuous motion
# PROBLEM: Loss of synchronisation on motor
#-----------------------------------------------
def start_motor(freq):
    INT_STEP.freq(freq)
    INT_STEP.duty_u16(32768)

def stop_motor():
    INT_STEP.duty_u16(0)
    sleep(0.002)

# ---- Test loop ----

while True:
    #print("Forward")
    stop_motor()
    sleep(0.01)
    INT_DIR.value(1)
    sleep(0.01)
    start_motor(1000)   # 1000 steps/sec (~1 revolution for 1.8° motor)
    sleep(stepdelay)
    stop_motor()
    led.toggle()   
    sleep(loopdelay)

    #print("Reverse")
    stop_motor()
    sleep(0.01)
    INT_DIR.value(0)
    sleep(0.01)
    start_motor(1000)   # 1000 steps/sec (~1 revolution for 1.8° motor)
    sleep(stepdelay)
    stop_motor()
    led.toggle()   
    sleep(loopdelay)

    #gc.disable          # clean memory