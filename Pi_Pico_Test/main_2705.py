# Raspberry pico specific function library calls
from machine import Pin
from machine import Pin, PWM
from machine import Pin, UART
from time import sleep

#--------------------------------------------
# Pin configuration and initial value setting
#--------------------------------------------
led = Pin("LED", Pin.OUT, value=1)      # RPI pico LED (toggles per direction change
VM_EN = Pin(22, Pin.OUT, value=1)       # Main motor Voltage, initial state OFF, value: '0'=ON '1'=OFF 
VVCCIO_EN = Pin(10, Pin.OUT, value=0)   # IO motor voltage, initial state OFF, value: '1'=ON '0'=OFF  
INT_STEP = Pin(16, Pin.OUT, value=0)    # Motor step pin,  initial state '0', pulse signal
INT_DIR = Pin(17, Pin.OUT, value=0)     # Motor direction pin,  initial state '0', value: '0'=CCW '1'=CW
MS2 = Pin(19, Pin.OUT, value=0)         # Motor stepsize select pin,  initial state '0'
MS1 = Pin(20, Pin.OUT, value=0)         # Motor direction pin,  initial state '0'
ENN = Pin(21, Pin.OUT, value=1)         # Motor enable pin,  initial state OFF, value: '1'=OFF '0'=ON 

#-----------------------------------------------
# Step: slower/faster -> increase/decrease delay
#-----------------------------------------------
def step(delay_us=800):
    print("Send one step pulse")
    INT_STEP.value(1)
    sleep(delay_us)
    INT_STEP.value(0)
    sleep(delay_us)

# ---- Test loop ----
while True:
    print("Forward")
    INT_DIR.value(1)

    for i in range(200):   # 200 steps (~1 revolution for 1.8° motor)
        step()
        
    led.toggle()
    sleep(1)

    print("Reverse")
    INT_DIR.value(0)

    for i in range(200):
        step()

    led.toggle()
    sleep(1)





# Set up PWM Pin
#pulse = machine.Pin(19)
#Pulse_pwm = machine.PWM(pulse)


# Small test program controlling exact pulse timing for motor tuning
#Pulse_pwm.freq(700) # 12kHz
#Duty_Cycle = round(65535 * 0.50) # 50% duty cycle
#Pulse_pwm.duty_u16(Duty_Cycle)

#x = input("Hit enter to end")
#Pulse_pwm.duty_u16(1)
#led.toggle()

#for i in range (2000): # number of repeating pulse train cycles, every cycle direction is changed
    
    #sleep(2)
    # CALCULATION 1 REVOLUTION
    # Motor = 1,8deg/step - 200 steps per rev pulses w timing according to sleep (ms)
    # Gear ration = 15 rev motor per 47 rev RF joint
    # Microstep ratio = 200 full steps x M = setting DT320, for example: 4000 microsteps = 20 x 200 steps per rev
    # value r = microstep setting 4000, gear ratio 47/15, 1,8deg per step = 20 x 200 x 47/15 = 12533 (rounded)
    # CALCULATION RPM
    # 1 step (pulse) = 4 (t) ms period so 1 revolution (Rt) = 12533 (r) x 4(t) ms = 50132 ms
    # RPM = Rt /(60*1000) = 0,8355 RPM
    #
    #or i in range(12500): 
    #for i in range(131072): 
        #pulse.value(1)
        #sleep(0.0001)
        #sleep(0.001)
        #pulse.value(0)
        #sleep(0.0001)
        #sleep(0.001)


#sleep(0.01)
    #dir.toggle()

