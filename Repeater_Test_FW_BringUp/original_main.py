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
MODO_SELECCIONADO = 3  
test_activo = False 
ultimo_estado_sw1 = 1  
ultimo_debounce_time = 0
errores_acumulados = 0
tiempo_inicio_test = 0  
test_sweep_active = False
instancia_sweep = None
CANAL_ACTIVO = "A"
DATA_RATE = 3

# --- DIRECCIONES I2C CONFIGURABLES (7-BIT) ---
DES_ADDR_7BIT = 0x6A  
SER_ADDR_7BIT = 0x40  

#-------------------------------------------------------------------------------------------

# Bus I2C0 de hardware — Canal A 
I2C0_SDA = 0   
I2C0_SCL = 1   
I2C0_FREQ = 100_000

# Bus I2C1 de hardware — Canal B
I2C1_SDA = 2   
I2C1_SCL = 3   
I2C1_FREQ = 100_000

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
hw.set_headstage_v(CS_DACA_ISOL, 4.5); hw.set_headstage_v(CS_DACB_ISOL, 4.5)
    
LED_GREEN.value(1); time.sleep(0.3); LED_GREEN.value(0)
LED_BLUE.value(0)
LED_RED.value(0)

escanear_e_identificar_i2c()

print("\n==========================================================")
print(f"⚙️ INICIANDO BUCLE AUTOMÁTICO ROTATIVO (3x A->B [9s] / 3x B->A [9s])")
print("==========================================================")

# Variables de control temporal y contador de ciclos rotativos (3 lecturas de 3s por dirección = 9s)
ref_tiempo_led = time.ticks_ms()
ref_tiempo_test = 0  
contador_ciclos = 0

# --- BUCLE PRINCIPAL ---
while True:
    tiempo_actual = time.ticks_ms()

    # 1. Parpadeo de LED de vida (10 Hz)
    if time.ticks_diff(tiempo_actual, ref_tiempo_led) >= 50:
        ref_tiempo_led = tiempo_actual
        LED_RPI.toggle()

    # 2. Ejecución periódica cada 3000 ms (3 segundos)
    if time.ticks_diff(tiempo_actual, ref_tiempo_test) >= 3000:
        ref_tiempo_test = tiempo_actual
        contador_ciclos += 1
        
        LED_BLUE.toggle() 

        # DETERMINACIÓN ROTATIVA DE DIRECCIÓN (3 ciclos A->B, luego 3 ciclos B->A)
        fase_rotacion = (contador_ciclos - 1) % 6
        if fase_rotacion < 3:
            CANAL_GENERADOR = "A"
            CANAL_RECEPTOR  = "B"
            num_subciclo = fase_rotacion + 1
        else:
            CANAL_GENERADOR = "B"
            CANAL_RECEPTOR  = "A"
            num_subciclo = fase_rotacion - 2

        # ASIGNACIÓN DINÁMICA DE CONTROLADORES
        if CANAL_GENERADOR == "A":
            ctrl_gen = serdes_A
            i2c_gen = i2c0_A
            cs_adc_gen = CS_ADCA_ISOL
            dbg_gen = dbg_A
        else:
            ctrl_gen = serdes_B
            i2c_gen = i2c1_B
            cs_adc_gen = CS_ADCB_ISOL
            dbg_gen = dbg_B

        if CANAL_RECEPTOR == "A":
            ctrl_rx = serdes_A
            i2c_rx = i2c0_A
            cs_adc_rx = CS_ADCA_ISOL
            dbg_rx = dbg_A
        else:
            ctrl_rx = serdes_B
            i2c_rx = i2c1_B
            cs_adc_rx = CS_ADCB_ISOL
            dbg_rx = dbg_B

        print("\n" + "="*65)
        print(f"🔄 [CICLO ROTATIVO]: MODO {MODO_SELECCIONADO} | GEN: Canal {CANAL_GENERADOR} -> RX: Canal {CANAL_RECEPTOR} (Muestra {num_subciclo}/3)")
        print("="*65)

        # ==============================================================================
        # MODO 4: BUCLE CRUZADO CON TELEMETRÍA DETALLADA Y ROTACIÓN AUTOMÁTICA
        # ==============================================================================
        if MODO_SELECCIONADO == 4:
            hw.set_channel_A_power_source(external=False) 
            hw.set_channel_B_power_source(external=False) 
            hw.set_headstage_v(CS_DACA_ISOL, 4.5)
            hw.set_headstage_v(CS_DACB_ISOL, 4.5)

            # 1. Tasa de Enlace (3 Gbps)
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0001, 0x44)
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x0001, 0x11)

            # 2. VPG en Serializador Generador (Banco VTX)
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0383, 0x00) 
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x024E, 0xE3) 
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x024F, 0x01) 
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0261, 0x08)
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0262, 0x98)
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0263, 0x04)
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0264, 0x65)
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0265, 0x07)
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0266, 0x80)
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0269, 0x04)
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x026A, 0x38)
            
            val_11_sergen = ctrl_gen._read_reg(SER_ADDR_7BIT, 0x0011)
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0011, (val_11_sergen if val_11_sergen is not None else 0x02) | 0x01)
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x14C8, 0x7F) 
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x14CE, 0x03) 
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x026B, 0x01) 

            # 3. Deserializador Receptor
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x0010, 0x20) 
            time.sleep_ms(20)
            val_11_desrx = ctrl_rx._read_reg(DES_ADDR_7BIT, 0x0011)
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x0011, (val_11_desrx if val_11_desrx is not None else 0x0A) | 0x01)
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x003F, 0x04) 
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x1417, 0x0E) 
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x141F, 0xA7) 
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x1418, 0x02) 
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x0018, 0x20) 
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x0010, 0x11) 
            
            # 4. Reseteo One-Shot
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0010, 0x20)
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x0010, 0x20)
            time.sleep_ms(200) 

            # --- EXTRACCIÓN DE DATOS DE ENLACE ---
            lock_link, lock_bcc = ctrl_rx.get_detailed_lock()
            raw_0013 = ctrl_rx._read_reg(DES_ADDR_7BIT, 0x0013)

            eom_margin = 0
            gain_step = 0  
            cable_code = 0

            if lock_link:
                try:
                    ctrl_rx._write_reg(DES_ADDR_7BIT, 0x1404, 0x4D) 
                    time.sleep_ms(30)
                    val_1407 = ctrl_rx._read_reg(DES_ADDR_7BIT, 0x1407)
                    if val_1407 is not None:
                        eom_margin = val_1407 & 0x7F
                    
                    aeq_raw = read_local_safe(i2c_rx, DES_ADDR_7BIT, 0x1412)
                    gain_step = (aeq_raw & 0x0F) if aeq_raw is not None else 0
                except:
                    pass

            try:
                line_raw = read_local_safe(i2c_rx, DES_ADDR_7BIT, 0x0026)
                cable_code = (line_raw & 0x07) if line_raw is not None else 0
            except:
                cable_code = 0

            mipi_in_status = read_local_safe(i2c_gen, SER_ADDR_7BIT, 0x0311)
            mipi_clk_detected = bool(mipi_in_status & 0x40) if mipi_in_status is not None else False                
            raw_str = f"0x{raw_0013:02X} | Binary: {raw_0013:08b}" if raw_0013 is not None else "NACK"

            reg_14c8 = ctrl_gen._read_reg(SER_ADDR_7BIT, 0x14C8)
            reg_14ce = ctrl_gen._read_reg(SER_ADDR_7BIT, 0x14CE)
            reg_ser_11 = ctrl_gen._read_reg(SER_ADDR_7BIT, 0x0011)
            reg_des_11 = ctrl_rx._read_reg(DES_ADDR_7BIT, 0x0011)
            reg_141f = ctrl_rx._read_reg(DES_ADDR_7BIT, 0x141F)
            reg_1418 = ctrl_rx._read_reg(DES_ADDR_7BIT, 0x1418)

            def fmt_reg_nibbles(val, func_desc):
                if val is not None:
                    b_str = f"{val:08b}"
                    return f"0x{val:02X} | Binary: {b_str[:4]} {b_str[4:]} ({func_desc})"
                else:
                    return "NACK / Read Error"

            # 1. REGISTROS SERDES
            print("-" * 65)
            print(f"  --- SERIALIZER {CANAL_GENERADOR} REGISTERS (Ser {CANAL_GENERADOR} - Gen) ---")
            print(f"  Register 0x0011 : {fmt_reg_nibbles(reg_ser_11, 'Cable Medium Type / Coax')}")
            print(f"  Register 0x14C8 : {fmt_reg_nibbles(reg_14c8, 'RF Amplitude Max')}")
            print(f"  Register 0x14CE : {fmt_reg_nibbles(reg_14ce, 'Pre-emphasis Control')}")
            print(f"  --- DESERIALIZER {CANAL_RECEPTOR} REGISTERS (Des {CANAL_RECEPTOR} - Rx) ---")
            print(f"  Register 0x0011 : {fmt_reg_nibbles(reg_des_11, 'Cable Medium Type / Coax')}")
            print(f"  Register 0x141F : {fmt_reg_nibbles(reg_141f, 'AGC Initial Gain G2')}")
            print(f"  Register 0x1418 : {fmt_reg_nibbles(reg_1418, 'VGA High Gain / Config')}")

            # 2. HARDWARE STRAPPING
            print("-" * 65)
            print("  --- HARDWARE STRAPPING (CFG0 / CFG1) ---")
            try:
                cfg_des_r0 = dbg_rx.read_reg(DES_ADDR_7BIT, 0x0000)
                cfg_des_r1 = dbg_rx.read_reg(DES_ADDR_7BIT, 0x0001)
                cfg_des_r11 = dbg_rx.read_reg(DES_ADDR_7BIT, 0x0011)
                
                cxtp_des = cfg_des_r11 & 0x01 if cfg_des_r11 is not None else 0
                rate_des = cfg_des_r1 & 0x03 if cfg_des_r1 is not None else 0
                rate_des_str = "6 Gbps" if rate_des == 2 else "3 Gbps" if rate_des == 1 else "Unknown"
                cable_des_str = "COAXIAL" if cxtp_des == 1 else "STP"

                cfg_ser_r0 = dbg_gen.read_reg(SER_ADDR_7BIT, 0x0000)
                cfg_ser_r1 = dbg_gen.read_reg(SER_ADDR_7BIT, 0x0001)
                cfg_ser_r11 = dbg_gen.read_reg(SER_ADDR_7BIT, 0x0011)

                cxtp_ser = cfg_ser_r11 & 0x01 if cfg_ser_r11 is not None else 0
                tx_rate_ser = (cfg_ser_r1 >> 2) & 0x03 if cfg_ser_r1 is not None else 0
                rate_ser_str = "6 Gbps" if tx_rate_ser == 2 else "3 Gbps" if tx_rate_ser == 1 else "Unknown"
                cable_ser_str = "COAXIAL" if cxtp_ser == 1 else "STP"

                print(f"  [Deserializer Des{CANAL_RECEPTOR} Straps]")
                print(f"  • Latched I2C Addr (0x0000) : 0x{cfg_des_r0:02X}" if cfg_des_r0 is not None else "  • I2C Addr: NACK")
                print(f"  • Latched Link Rate (0x0001): {rate_des_str}")
                print(f"  • Latched Medium Type (0x0011): {cable_des_str}")
                
                print(f"\n  [Serializer Ser{CANAL_GENERADOR} Straps]")
                print(f"  • Latched I2C Addr (0x0000) : 0x{cfg_ser_r0:02X}" if cfg_ser_r0 is not None else "  • I2C Addr: NACK")
                print(f"  • Latched Forward Rate (0x0001): {rate_ser_str}")
                print(f"  • Latched Medium Type (0x0011): {cable_ser_str}")
            except:
                print("  • Hardware Strapping Read Error")

            # 3. TELEMETRÍA Y ALIMENTACIÓN
            try: v_a, i_a, _ = hw.read_telemetry(CS_ADCA_ISOL)
            except: v_a, i_a = 0.0, 0.0
                
            try: v_b, i_b, _ = hw.read_telemetry(CS_ADCB_ISOL)
            except: v_b, i_b = 0.0, 0.0
            
            try:
                u32_gpio = hw.mcp_read(ADDR_U32, GPIO)
                pwdn_ser_a = bool(u32_gpio & 0x04)
                pwdn_des_a = bool(u32_gpio & 0x08)
                pwdn_ser_b = bool(u32_gpio & 0x10)
                pwdn_des_b = bool(u32_gpio & 0x20)
            except:
                pwdn_ser_a = pwdn_des_a = pwdn_ser_b = pwdn_des_b = False

            i_a_str = f"{i_a:.1f}mA" if i_a > 1.0 else "No Headstage"
            i_b_str = f"{i_b:.1f}mA" if i_b > 1.0 else "No Headstage"

            print("-" * 65)
            print("  --- TELEMETRÍA DE HARDWARE Y ALIMENTACIÓN (POWER & PWDN) ---")
            print(f"  ⚡ Headstage A Power Supply : {v_a:.2f}V | {i_a_str}")
            print(f"  ⚡ Headstage B Power Supply : {v_b:.2f}V | {i_b_str}")
            print(f"  🔌 Hardware PWDN Channel A  : DES_A: {'[ HIGH (ON) ]' if pwdn_des_a else '[ RESET ]'} | SER_A: {'[ HIGH (ON) ]' if pwdn_ser_a else '[ RESET ]'}")
            print(f"  🔌 Hardware PWDN Channel B  : DES_B: {'[ HIGH (ON) ]' if pwdn_des_b else '[ RESET ]'} | SER_B: {'[ HIGH (ON) ]' if pwdn_ser_b else '[ RESET ]'}")

            print("-" * 65)
            print("  --- HEALTH REGISTERS (NATIVE CHIP STATUS) ---")
            health_blocks = [
                ("DesA1 (Bus A - Deserializer)", serdes_A, DES_ADDR_7BIT, 0x0013, "Link Lock / Error Status"),
                ("SerA1 (Bus A - Serializer)  ", serdes_A, SER_ADDR_7BIT, 0x0008, "Power / PORZ Status"),
                ("DesB1 (Bus B - Deserializer)", serdes_B, DES_ADDR_7BIT, 0x0013, "Link Lock / Error Status"),
                ("SerB1 (Bus B - Serializer)  ", serdes_B, SER_ADDR_7BIT, 0x0008, "Power / PORZ Status"),
                ("DesA2 (Bus A - Deserializer)", serdes_A, DES_ADDR_7BIT, 0x0013, "Link Lock / Error Status"),
                ("SerA2 (Bus A - Serializer)  ", serdes_A, SER_ADDR_7BIT, 0x0008, "Power / PORZ Status"),
                ("DesB2 (Bus B - Deserializer)", serdes_B, DES_ADDR_7BIT, 0x0013, "Link Lock / Error Status"),
                ("SerB2 (Bus B - Serializer)  ", serdes_B, SER_ADDR_7BIT, 0x0008, "Power / PORZ Status")
            ]

            for block_name, ctrl_inst, dev_addr, health_reg, reg_desc in health_blocks:
                val_health = ctrl_inst._read_reg(dev_addr, health_reg)
                if val_health is not None:
                    b_str = f"{val_health:08b}"
                    print(f"  • {block_name} [Reg 0x{health_reg:04X}] : 0x{val_health:02X} | Binary: {b_str[:4]} {b_str[4:]} ({reg_desc})")
                else:
                    print(f"  • {block_name} [Reg 0x{health_reg:04X}] : NACK / Read Error")

            # 4. RESULTADO PRINCIPAL DEL ENLACE (UBICADO ABAJO DEL TODO)
            print("\n" + "="*65)
            print(f"🖥️ AUTOMATIC LOOP MONITOR [Ser {CANAL_GENERADOR} (Gen) -> Coax -> Des {CANAL_RECEPTOR} (Rx)] | Muestra {num_subciclo}/3")
            print("="*65)
            print(f"  🔍 Des {CANAL_RECEPTOR} Register 0x0013 Raw: {raw_str} (Link Status / Lock)")
            print(f"  🔒 Des {CANAL_RECEPTOR} Link Status (0x6A) : LINK_LOCK = {'[ OK ]' if lock_link else '[ FAIL ]'} | BCC = {'[ OK ]' if lock_bcc else '[ FAIL ]'}")
            print(f"  📊 EOM Eye Margin (0x1407)  : {eom_margin} / 127 Units {'[ 🟢 OK ]' if eom_margin >= 15 else '[ 🟡 MARGINAL ]' if eom_margin > 0 else '[ 🔴 CRITICAL ]'}")
            print(f"    - CTLE AEQ Gain (0x1412)  : Step {gain_step} of 15")
            print(f"    - Cable Impedance (0x0026): Code 0x{cable_code:02X} {'[ 🟢 50 Ohm OK ]' if cable_code == 0x02 else '[ 🔴 MISMATCHED ]'}")
            print(f"  📤 Serializer {CANAL_GENERADOR} (0x40)      : MIPI RX Status (0x0311): {'0x{:02X}'.format(mipi_in_status) if mipi_in_status is not None else 'NACK'}")
            print(f"    - MIPI CSI-2 Clock        : {'[ OK (0x40) ]' if mipi_clk_detected else '[ SEARCHING... ]'}")
            
            if lock_link and eom_margin >= 10:
                LED_GREEN.value(1)
                LED_RED.value(0)
                LED_BLUE.toggle()
                print("  🟢 STATUS: RF PHYSICAL LINK 100% CONFIRMED & VPG STREAMING")
            else:
                LED_GREEN.value(0)
                LED_RED.value(1)
                LED_BLUE.value(0)
                print("  🔴 ALERT: NO RF LINK OR CALIBRATING EQUALIZER...")

            print("="*65)

        # ==============================================================================
        # MODO 5: CAPTURA AUTOMÁTICA DE DIAGRAMA DE OJO (EOM) ROTATIVO CON BOOST COMPLETO
        # ==============================================================================
        elif MODO_SELECCIONADO == 5:
            hw.set_channel_A_power_source(external=False) 
            hw.set_channel_B_power_source(external=False) 
            hw.set_headstage_v(CS_DACA_ISOL, 4.5)
            hw.set_headstage_v(CS_DACB_ISOL, 4.5)

            # 1. Configuración de tasa y VPG en transmisor
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0001, 0x44)
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x0001, 0x11)
            vpg_test.enable_serializer_vpg(CANAL_GENERADOR)

            # 2. Configuración PHY y sensibilidad en el receptor RX (Boost completo de RF)
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x0010, 0x20) 
            time.sleep_ms(20)
            val_11_desrx = ctrl_rx._read_reg(DES_ADDR_7BIT, 0x0011)
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x0011, (val_11_desrx if val_11_desrx is not None else 0x0A) | 0x01)
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x003F, 0x04) 
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x1417, 0x0E) # Sensibilidad 1.5 GHz
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x141F, 0xA7) 
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x1418, 0x02) 
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x0018, 0x20) 
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x0010, 0x11) 

            # 3. Reseteo de sincronización
            ctrl_gen._write_reg(SER_ADDR_7BIT, 0x0010, 0x20)
            ctrl_rx._write_reg(DES_ADDR_7BIT, 0x0010, 0x20)
            time.sleep_ms(300)

            # 4. Mapeo del diagrama de ojo (renderiza siempre en ASCII, abierto o cerrado)
            SerDes_Eye_test.ejecutar_eye_mapping(i2c_rx, DES_ADDR_7BIT, CANAL_RECEPTOR)

            lock_link, _ = ctrl_rx.get_detailed_lock()
            if lock_link:
                LED_GREEN.value(1); LED_RED.value(0)
            else:
                LED_GREEN.value(0); LED_RED.value(1)

            vpg_test.disable_vpg(CANAL_GENERADOR)
            print("="*65)

    time.sleep_ms(5)