# main.py 
# import os; os.listdir()
# ==============================================================================
# NXT REPEATER - CONFIGURACIÓN DE BANCO DE PRUEBAS (DUAL-PROTOTYPE / MONO-PLACA)
# ==============================================================================
# Este firmware unificado permite controlar, depurar y diagnosticar el hardware
# del NXT Repeater (RP2040 + MAX96716A + MAX96717) de forma local o en cascada.
#
# El comportamiento global de la placa emisora de estímulos se define con:
# -> ES_EMISOR_VPG = True  (Prototipo 1 / Generador de Estímulo)
# -> ES_EMISOR_VPG = False (Prototipo 2 / Analizador de Paso y Enlace)
#
# ==============================================================================
#          ⚠️ ADVERTENCIA DE SEGURIDAD: CALIBRACIÓN DEL CABLE COAXIAL (TETHER)
# ==============================================================================
# Para calibrar de forma segura el "Punto Dulce" (Sweet Spot) de alimentación del
# headstage (LTC2601 DAC / Modo 3) y la integridad de señal (SI), es MANDATORIO
# utilizar el mismo cable coaxial ultrafino (5 a 10m, diam. 0.2mm) que se empleará
# físicamente con el animal durante el experimento real.
#
# ¿Por qué es obligatorio?
# 1. Compensación Óhmica (I*R): Los cables de animal tienen una resistencia serie
#    de 10 a 30 Ohms. Con el consumo del headstage (~150mA), provocan una caída de
#    tensión de hasta 1.5V. Si calibras con un cable de laboratorio corto (caída ~0V),
#    fijarás una tensión del DAC demasiado baja. Al conectar el cable real del
#    animal, el headstage sufrirá una subtensión (brownout) y el GMSL2 no hará LOCK.
# 2. Compensación de Microondas (RF): La atenuación a 3 GHz del cable ultrafino es
#    elevada. Calibrar con el cable definitivo permite al ecualizador adaptativo
#    (AEQ) del Deserializador compensar las pérdidas reales de inserción del canal.
# ==============================================================================
# ==============================================================================
#                    RESUMEN DE MODOS DE PRUEBA Y TEST SELECCIONADOS
# ==============================================================================
#  MODO | NOMBRE DEL TEST             | CONEXIÓN COAXIAL REQUERIDA   | ACCIÓN SW1
# ------+-----------------------------+------------------------------+--------------
#   0   | Monitoreo Pasivo Normal     | Cualquiera o ninguna         | Alterna ON/OFF
#       | (Muestra Locks y Telemetría)|                              | el monitoreo.
# ------+-----------------------------+------------------------------+--------------
#   1   | Test BERT PRBS7             | Lazo cerrado local o cruzado | Inyecta PRBS7
#       | (Bit Error Rate Test)       | (ej. QBSC_CHA -> HSA)        | desde el TX.
# ------+-----------------------------+------------------------------+--------------
#   2   | Test VPG (Video Pattern Gen)| Lazo cerrado local o cruzado | Genera barras
#       | (Barras de Colores 1080p)   | (ej. QBSC_CHA -> HSA)        | en Des y mide
#       |                             |                              | error en Ser.
# ------+-----------------------------+------------------------------+--------------
#   3   | Barrido Asíncrono de Margen | Lazo cerrado local o cruzado | Modula DAC
#       | (Sweep de Voltaje de LDO)   | (ej. QBSC_CHA -> HSA)        | de 3.0 a 5.5V
#       |                             |                              | buscando LOCK.
# ------+-----------------------------+------------------------------+--------------
#   4   | Bucle Cruzado Mono-PlACA    | Cruzado en la misma placa    | Alterna 3x (A->B)
#       | (QBSC_CHA -> HSB o vicev.)  | (QBSC_CHA -> HSB)            | y 3x (B->A) cada
#       |                             |                              | 3s (9s por vía).
# ------+-----------------------------+------------------------------+--------------
#   5   | Diagrama de Ojo en Chip     | Lazo cerrado local o cruzado | Captura RLMS
#       | (EOM PHY Status - RLMS)     | (ej. QBSC_CHA -> HSA)        | y renderiza
#       |                             |                              | ojo ASCII.
# ==============================================================================
#
# FEEDBACK ÓPTICO DE LOS LEDS DE LA PLACA (En ejecución de Test Activo):
# - LED AZUL parpadeando: Prueba activa en caliente (BERT, VPG o Barrido).
# - LED VERDE (en reposo / fin de test): Estado LOCK OK. 0 errores detectados.
# - LED ROJO (en reposo / fin de test): Fallo de LOCK o errores CSI-2 acumulados.
# ==============================================================================
import sys
if '/' not in sys.path:
    sys.path.append('/')

import machine
import time
import SerDes_Eye_test
from board_hw import BoardHardware, ADDR_U32, GPIO
from serdes_lib import SerDesController
from serdes_diag import SerDesDiagnostics  # Suite de diagnóstico para el laboratorio
from serdes_vpg import SerDesVideoPatternTest
from machine import Pin, Timer
from serdes_reg_debug import GMSLRegisterDebugger

# --- PLACA NPNXT_RPTST_00 / Raspberry Pi Pico (RP2040) ---
BOARD_NAME = "NPNXT_RPTST_00"

#-------------------------------------------------------------------------------------------
# --- CONFIGURACION PLACA NPNXT_RPTST_00 ---
#-------------------------------------------------------------------------------------------
# NOTA: Los canales de Generador y Receptor se conmutan automáticamente en el bucle principal.
CANAL_GENERADOR = "A" 
CANAL_RECEPTOR  = "B" 

BREAKPOINTS_ACTIVE = False #False #True 
ES_EMISOR_VPG = False 
MODO_SELECCIONADO = 0  
test_activo = False 
ultimo_estado_sw1 = 1  
ultimo_debounce_time = 0
errores_acumulados = 0
tiempo_inicio_test = 0  
test_sweep_active = False
instancia_sweep = None
CANAL_ACTIVO = "B"
DATA_RATE = 3

# --- DIRECCIONES I2C CONFIGURABLES (7-BIT) ---
DES_ADDR_7BIT = 0x6A  
SER_ADDR_7BIT = 0x40  

#-------------------------------------------------------------------------------------------

# Bus I2C0 de hardware — Canal A 
I2C0_SDA = 0   
I2C0_SCL = 1   
I2C0_FREQ = 400_000

# Bus I2C1 de hardware — Canal B
I2C1_SDA = 2   
I2C1_SCL = 3   
I2C1_FREQ = 400_000

# --- CONFIGURACIÓN DE PINES GPIO RP2040 ---
PWDNB_SDA_ISOL = machine.Pin(20, machine.Pin.IN, machine.Pin.PULL_UP)
PWDNB_SDB_ISOL = machine.Pin(19, machine.Pin.IN, machine.Pin.PULL_UP)
CSI_SPI        = machine.Pin(5, machine.Pin.OUT)
CS_DACA_ISOL   = machine.Pin(10, machine.Pin.OUT)
CS_DACB_ISOL   = machine.Pin(11, machine.Pin.OUT)
CS_ADCA_ISOL   = machine.Pin(15, machine.Pin.OUT)
CS_ADCB_ISOL   = machine.Pin(22, machine.Pin.OUT)
PS_ISOL_CTRL   = machine.Pin(14, machine.Pin.OUT)
LED_RED, LED_GREEN, LED_BLUE = machine.Pin(16, machine.Pin.OUT), machine.Pin(17, machine.Pin.OUT), machine.Pin(18, machine.Pin.OUT)
SW1 = machine.Pin(28, machine.Pin.IN, machine.Pin.PULL_UP)
LED_RPI = Pin(25, Pin.OUT)

# ==============================================================================
#    Turn On the isolated power supply
# ==============================================================================
PS_ISOL_CTRL.value(1)  
time.sleep_ms(300)

# --- INICIALIZACIÓN DE BUSES DE COMUNICACIÓN ---
i2c0_A = machine.I2C(0, scl=machine.Pin(I2C0_SCL), sda=machine.Pin(I2C0_SDA), freq=I2C0_FREQ)
i2c1_B = machine.I2C(1, scl=machine.Pin(I2C1_SCL), sda=machine.Pin(I2C1_SDA), freq=I2C1_FREQ)

# --- CORRECCIÓN: DEFINICIÓN DE i2c_canales REQUERIDA POR LAS FUNCIONES ---
i2c_canales = {
    "A": i2c0_A,
    "B": i2c1_B
}

spi = machine.SPI(0, baudrate=1000000, polarity=0, phase=0, sck=machine.Pin(6), mosi=machine.Pin(7), miso=machine.Pin(4))

for cs in [CSI_SPI, CS_DACA_ISOL, CS_DACB_ISOL, CS_ADCA_ISOL, CS_ADCB_ISOL]: cs.value(1)

# --- INSTANCIACIÓN DE CONTROLADORES ---
hw = BoardHardware(spi, CSI_SPI, CS_DACA_ISOL, CS_DACB_ISOL, CS_ADCA_ISOL, CS_ADCB_ISOL)
serdes_A = SerDesController(i2c0_A, des_addr=DES_ADDR_7BIT, ser_addr=SER_ADDR_7BIT)
serdes_B = SerDesController(i2c1_B, des_addr=DES_ADDR_7BIT, ser_addr=SER_ADDR_7BIT)
diag = SerDesDiagnostics(serdes_A, serdes_B, hw)
vpg_test = SerDesVideoPatternTest(serdes_A, serdes_B, hw)
dbg_A = GMSLRegisterDebugger(i2c0_A, des_addr=DES_ADDR_7BIT)  
dbg_B = GMSLRegisterDebugger(i2c1_B, des_addr=SER_ADDR_7BIT)

# --- FUNCIONES DE APOYO ---
def read_local_safe(i2c_bus, dev_addr, reg, retries=3):
    """Realiza una lectura segura de registro de 16 bits sin Repeated Start y con reintentos."""
    reg_buf = bytearray([(reg >> 8) & 0xFF, reg & 0xFF])
    for _ in range(retries):
        try:
            i2c_bus.writeto(dev_addr, reg_buf)
            time.sleep_ms(10)
            res = i2c_bus.readfrom(dev_addr, 1)
            return res[0]
        except OSError:
            time.sleep_ms(10)
    return None

def scan_i2c(bus, name):
    print(f"Scanning I2C Channel {name}...")
    try:
        devices = bus.scan()
        for dev in devices: print(f"  - 0x{dev:02X}")
    except Exception as e: print(f"  Error: {e}")

def escanear_e_identificar_i2c():
    mapa_comun = { DES_ADDR_7BIT: "MAX96716A Deserializador", SER_ADDR_7BIT: "MAX96717 Serializador" }
    mapa_canal_a = {0x50: "EEPROM A"}; mapa_canal_a.update(mapa_comun)
    mapa_canal_b = {0x51: "EEPROM B"}; mapa_canal_b.update(mapa_comun)
    for n, b, m in [("A", i2c0_A, mapa_canal_a), ("B", i2c1_B, mapa_canal_b)]:
        print(f"\n─── Escaneando Canal {n}... ───")
        try:
            for addr in b.scan(): print(f"  • 0x{addr:02X} -> {m.get(addr, 'Desconocido')}")
        except: pass

def breakpoint(label=""):
    """
    Punto de interrupción físico controlable.
    Si BREAKPOINTS_ACTIVE es False, la función no hace nada y el programa continúa.
    """
    if not BREAKPOINTS_ACTIVE:
        if label:
            print(f"[DEBUG]: Pasando por breakpoint ignorado -> '{label}'")
        return

    escanear_e_identificar_i2c()

    print("\n" + "="*50)
    if label:
        print(f"[BREAKPOINT - {label}]: Programa DETENIDO.")
    else:
        print("[BREAKPOINT]: Programa DETENIDO.")
    print("-> Presiona SW1 para continuar...")
    print("="*50 + "\n")
    
    while SW1.value() == 1:
        time.sleep_ms(10)
    time.sleep_ms(100)
    while SW1.value() == 0:
        time.sleep_ms(10)
    time.sleep_ms(100)
    print("[INFO]: Breakpoint liberado. Continuing execution...\n")


# --- SECUENCIA DE ARRANQUE ---
hw.mcp_global_init()
hw.setup_expanders()
rptr_a_ok = hw.power_on_channel_A(PWDNB_SDA_ISOL)
rptr_b_ok = hw.power_on_channel_B(PWDNB_SDB_ISOL)
time.sleep_ms(50)
if rptr_a_ok: hw.ina239_configure(CS_ADCA_ISOL, "A")
if rptr_b_ok: hw.ina239_configure(CS_ADCB_ISOL, "B")
hw.set_headstage_v(CS_DACA_ISOL, 5.0);
hw.set_headstage_v(CS_DACB_ISOL, 5.0);
hw.set_channel_A_power_source(external=False)
hw.set_channel_B_power_source(external=False)
    
LED_GREEN.value(1); time.sleep(0.3); LED_GREEN.value(0)
LED_BLUE.value(0)
LED_RED.value(0)

while True:
    LED_RPI.toggle()
    time.sleep(1)