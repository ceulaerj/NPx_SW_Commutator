#-----------------------------------------------
# Raspberry pico specific function library calls
#-----------------------------------------------
from machine import Pin
from machine import Pin, PWM
from machine import Pin, UART
from time import sleep
from time import sleep_us

#------------------------------------------------------------------------
# MOTOR DRIVER TMC2209 BOARD: Pin configuration and initial value setting
#------------------------------------------------------------------------
led = Pin("LED", Pin.OUT, value=0)      # RPI pico LED (toggles per direction change
VM_EN = Pin(22, Pin.OUT, value=1)       # Main motor Voltage, initial state OFF, value: '0'=ON '1'=OFF 
VVCCIO_EN = Pin(10, Pin.OUT, value=0)   # IO motor voltage, initial state OFF, value: '1'=ON '0'=OFF  
INT_STEP = Pin(16, Pin.OUT, value=0)    # Motor step pin,  initial state '0', pulse signal
INT_DIR = Pin(17, Pin.OUT, value=0)     # Motor direction pin,  initial state '0', value: '0'=CCW '1'=CW
MS2 = Pin(19, Pin.OUT, value=0)         # Motor stepsize select pin,  initial state '0'
MS1 = Pin(20, Pin.OUT, value=0)         # Motor direction pin,  initial state '0'
ENN = Pin(21, Pin.OUT, value=1)         # Motor enable pin,  initial state OFF, value: '1'=OFF '0'=ON 
MD_UART = UART(0, baudrate=115200, tx=Pin(8), rx=Pin(9))    # Motor UART, use UART1 on GP8:GP9
gdelay = 0.5                            # global dalay 1/2 second
loopdelay = 1                           # loop dalay 1 second

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
# TMC2209 UART address (default 0)
#-------------------------------------------------------------------
VM_EN.value(0)
led.toggle()
sleep(gdelay)
VVCCIO_EN.value(1)
led.toggle()
sleep(gdelay)
ENN.value(0)
MS1.value(0)
MS2.value(0)
led.toggle()
DRIVER_ADDR = 0x00
led.toggle()
sleep(gdelay)


# ------------------------------------
# CRC calculation (TMC2209 specific)
# ------------------------------------
def calc_crc(data):
    crc = 0
    for byte in data:
        for i in range(8):
            if (crc >> 7) ^ (byte >> i & 0x01):
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc

# -------------------------
# Write register function
# -------------------------
def tmc_write(register, value):
    datagram = bytearray(8)
    datagram[0] = 0x05                # sync
    datagram[1] = DRIVER_ADDR
    datagram[2] = register | 0x80     # write bit
    datagram[3] = (value >> 24) & 0xFF
    datagram[4] = (value >> 16) & 0xFF
    datagram[5] = (value >> 8) & 0xFF
    datagram[6] = value & 0xFF
    datagram[7] = calc_crc(datagram[:7])

    MD_UART.write(datagram)

# ----------------------
# TMC2209 Initialization
# ----------------------
def tmc_init():
    # Enable stealthChop (silent mode)
    tmc_write(0x10, 0x00000000)   # GCONF: default silent mode

    # Set current (IHOLD_IRUN register)
    # IHOLD=8, IRUN=20, IHOLDDELAY=4
    ihold = 8
    irun = 20
    iholddelay = 4
    value = (iholddelay << 16) | (irun << 8) | ihold
    tmc_write(0x10, value)

    # CHOPCONF (stealthChop config)
    tmc_write(0x6C, 0x10000053)

    print("TMC2209 initialized (silent mode)")

# ----------------------
# Step pulse
# ----------------------
def step(delay_us=800):
    INT_STEP.value(1)
    sleep_us(delay_us)
    INT_STEP.value(0)
    sleep_us(delay_us)

# ----------------------
# Move function
# ----------------------
def move(steps, direction, delay=800):
    INT_DIR.value(direction)
    for _ in range(steps):
        step(delay)

# ----------------------
# Main
# ----------------------
tmc_init()

while True:
    print("Forward (silent)")
    move(400, 1, 600)

    sleep(loopdelay)

    print("Reverse (silent)")
    move(400, 0, 600)

    sleep(loopdelay)
