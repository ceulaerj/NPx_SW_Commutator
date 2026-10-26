#------------------------------------------------------------------------------------------
# Logic to control stepper using TMC2209
# Contains fixed HW settings for microstepping and 1 revolution with speed control
# Input variables: Direction, 
#-----------------------------------------------
# Raspberry pico specific function library calls
#-----------------------------------------------
from machine import Pin
from time import sleep
import rp2


# -------------------------------------------------------------------------------------
# PIO program: generates clean INT_STEP pulses (7 instruction: set H, delay, set L, delay)
# INT_STEP pulse frequency = freq / No cycles
# type ignore is to ignore warnings because pylance does not know the syntax
# -------------------------------------------------------------------------------------
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def stepper():
    pull()                      # type: ignore #load step count
    mov(x, osr)                 # type: ignore #copy to x

    label("loop")               # type: ignore
    set(pins, 1) [1]            # type: ignore # STEP HIGH (short pulse), 2 cycles
    nop()                       # type: ignore # delay, 1 cycle
    set(pins, 0) [1]            # type: ignore # STEP LOW, 2 cycles
    nop()                       # type: ignore # delay, 1 cycle

    jmp(x_dec, "loop")          # type: ignore #loop until x=0, 1 cycle
    
    irq(0)                      # type: ignore # signal done
    set(pins, 0)                # type: ignore # ensure clean end state

cycles = 7                      # sum of PIO cycles in function stepper

#------------------------------------------------------------------------
# MOTOR DRIVER TMC2209 BOARD: Pin configuration and initial value setting
#------------------------------------------------------------------------
led = Pin("LED", Pin.OUT, value=1)      # RPI pico LED (toggles per direction change)

VM_EN = Pin(22, Pin.OUT, value=1)       # Main motor Voltage, initial state OFF, value: '0'=ON '1'=OFF 
VCCIO_EN = Pin(10, Pin.OUT, value=0)    # IO motor voltage, initial state OFF, value: '1'=ON '0'=OFF  

INT_STEP = Pin(20, Pin.OUT, value=0)    # Motor step pin, timer pulse, initial state '0'
INT_DIR = Pin(21, Pin.OUT, value=0)     # Motor direction pin,  initial state '0', value: '0'=CCW '1'=CW

MS2 = Pin(18, Pin.OUT, value=0)         # Motor stepsize 0 select pin,  initial state '0'
MS1 = Pin(16, Pin.OUT, value=0)         # Motor stepsize 1 select pin,  initial state '0'

ENN = Pin(17, Pin.OUT, value=1)         # Motor enable pin,  initial state OFF, value: '1'=OFF '0'=ON 


# -------------------------------------------------------------
# Create PIO State Machine
# -------------------------------------------------------------
done = False

def irq_handler(sm):
    global done
    done = True

sm = rp2.StateMachine(
    0,
    stepper,
    freq=20000,            # initial frequency (will change dynamically)
    set_base=INT_STEP      # STEP pin controlled by PIO
)

sm.irq(irq_handler)
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
# Timing parameters
gdelay = 0.5                            # global dalay 1/2 second
loopdelay = 0.01                        # loop delay 10 mseconds
# motor control parameters
belt_ratio = 2.05                          # ratio of belt drive towards slipring
#msteps = 6400                           # revolution angle = msteps*1.8°/(16*2) steps (1/16 microstep & only edge pulse latching)
msteps = int(6400*belt_ratio)                # 1x 360° revolution on SLIPRING
speed = 5625                             # speed setting => freq = 2x speed / No steps
#speed = 11250                            # speed setting => 50 RPM ON SLIPRING
direction = 1                           # 1 = CCW ; 0 = CW
# Motor Initialisation
VM_EN.value(0)          # Enable main motor voltage
sleep(gdelay)           # Wait to settle

VCCIO_EN.value(1)       # Enable Motor VCIO
sleep(gdelay)           # Wait to settle

ENN.value(0)            # Driver Enable
MS1.value(1)            # Microstep set 1
MS2.value(0)            # Microstep set 2
sleep(gdelay)           # Wait to settle


# -------------------------------------------------------------
# PIO-based motor control functions
# -------------------------------------------------------------

def move_steps(steps, steps_per_sec):
    global sm, done

    # Convert to PIO clock frequency
    # 1 step = 7 cycles
    sfreq = steps_per_sec * cycles   # PIO clock = speed x cycles

    sm.active(0)
    
# Recreate SM with new frequency, step clock = PIO clock / PIO cycles
    sm = rp2.StateMachine(
        0,
        stepper,
        freq=sfreq,
        set_base=INT_STEP
    )

    sm.irq(irq_handler)   # ✅ reattach IRQ


    done = False

    sm.put(steps)
    sm.active(1)

    # Wait until PIO signals completion
    while not done:
        pass

    sm.active(0)
    INT_STEP.value(0)

# Safe direction switching (VERY important)
def set_direction(direction):
    sm.active(0)              # ensure no pulses
    INT_STEP.value(0)

    sleep(0.005)              # let signal settle
    INT_DIR.value(direction)
    sleep(0.002)              # TMC2209 DIR setup time

# ---- Test loop ----

while True:
#for _ in range(1):
 
    # ---- CCW ----
    direction = 1
    sleep(loopdelay)
    set_direction(direction)

    move_steps(msteps,speed)
    led.toggle()
    sleep(loopdelay)

    # ---- Reverse ----
    direction = 0
    sleep(loopdelay)
    set_direction(direction)

    move_steps(msteps,speed)
    led.toggle()
    sleep(loopdelay)

#INT_STEP.value(0)
