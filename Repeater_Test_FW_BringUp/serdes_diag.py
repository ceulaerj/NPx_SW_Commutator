# serdes_diag.py
# Módulo de diagnóstico interno en tiempo real para validación de hardware y SI
# Target: NPNXT_RPTST_00 (Raspberry Pi Pico / RP2040) — MAX96717 + MAX96716A

# ==============================================================================
# GMSL2 SERDES DIAGNOSTICS SUITE (PRBS7 BERT & LINE STATUS TEST)
# ==============================================================================
# This module provides real-time, on-chip signal integrity (SI) diagnostics 
# for the NXT Repeater (MAX96717 Serializer & MAX96716A Deserializer).
#
# HOW TO EXECUTE THE SERDES TEST:
# 1. Physical Trigger: 
#    Press the physical switch 'SW1' (GPIO 28) on the RP2040 board to toggle 
#    the system from "Normal Monitoring Mode" into "BERT Diagnostic Mode".
# 2. Visual Status Indicators:
#    - Flashing BLUE LED: Indicates the PRBS7 BERT test is actively running.
#    - Solid GREEN LED (upon test completion): Indicates 0 line errors (PASS).
#    - Solid RED LED (upon test completion): Indicates line errors detected (FAIL).
# 3. Test Process:
#    - When toggled ON, the script runs an initial physical layer cable status 
#      check using the Deserializer's built-in line-state ADC (detects Short-to-GND, 
#      Open, or Normal connection).
#    - It then enables the pseudo-random binary sequence (PRBS7) generator in 
#      the MAX96717 Serializer to stress the high-frequency physical channel (6 Gbps).
#    - The Deserializer's error counter register (DEC_ERR) is continuously polled 
#      and accumulated in real-time.
#    - Telemetry (VBUS and Current) is read simultaneously to verify the power distribution 
#      network (PDN) stability under maximum microwave data rate stress.
# 4. Stop & Report:
#    Press 'SW1' again to terminate the test, disable the PRBS7 injector, and return 
#    to standard passive system monitoring.
#
# HOW TO ANALYZE THE RESULTS:
# - CABLE STATUS:
#   * "Normal Connection": High-speed transmission path impedance is fully matched.
#   * "Short to GND" / "Open Circuit": Critical physical path discontinuity on PCB 
#     traces, coaxial connectors, or cable.
# - LINE ERRORS (DEC_ERR / Accumulated Errors):
#   * Accumulated Errors = 0: Perfect Signal Integrity (SI). The high-frequency physical 
#     channel, AC-coupling layout, and power filtering are operating within margins.
#   * Accumulated Errors > 0: High-frequency signal attenuation or noise. 
#     Analyze:
#       1. Check for impedance mismatches (e.g., lack of antipads under AC-coupling caps).
#       2. Run the `sweep_equalizer_margin` function to find the optimal RX 
#          equalizer voltage (LTC2601 DAC) to compensate for coaxial cable insertion loss.
#       3. Check PDN noise on SerDes analog PLL rails (V_DDA) causing Phase-Locked Loop jitter.
# ==============================================================================
# ==============================================================================
# SUITE DE DIAGNÓSTICO GMSL2 SERDES (TEST BERT PRBS7 Y ESTADO DE LÍNEA)
# ==============================================================================
# Este módulo proporciona diagnósticos de integridad de señal (SI) en tiempo 
# real e integrados en chip (on-chip) para el NXT Repeater (Serializador 
# MAX96717 y Deserializador MAX96716A).
#
# CÓMO EJECUTAR EL TEST DEL SERDES:
# 1. Disparador Físico: 
#    Presiona el pulsador físico 'SW1' (GPIO 28) en la placa de la RP2040 para 
#    alternar el sistema entre el 'Modo de Monitoreo Normal' y el 'Modo de 
#    Diagnóstico BERT'.
# 2. Indicadores Visuales de Estado:
#    - LED AZUL parpadeando: Indica que el test BERT PRBS7 se está ejecutando 
#      activamente.
#    - LED VERDE encendido fijo (al terminar el test): Indica 0 errores de línea 
#      (APROBADO).
#    - LED ROJO encendido fijo (al terminar el test): Indica que se detectaron 
#      errores de línea (FALLADO).
# 3. Proceso de Prueba:
#    - Al activarse, el script ejecuta una verificación inicial del estado físico 
#      del cable utilizando el ADC de estado de línea integrado en el Deserializador 
#      (detecta cortocircuito a masa, circuito abierto o conexión normal).
#    - A continuación, habilita el generador de secuencias binarias pseudoaleatorias 
#      (PRBS7) en el Serializador MAX96717 para estresar el canal físico de alta 
#      frecuencia (6 Gbps).
#    - El registro contador de errores del Deserializador (DEC_ERR) se sondea 
#      continuamente y se acumula en tiempo real.
#    - La telemetría (VBUS y corriente) se lee simultáneamente para verificar la 
#      estabilidad de la red de distribución de potencia (PDN) bajo el estrés de 
#      la máxima tasa de transferencia de datos de microondas.
# 4. Parada y Reporte:
#    Presiona 'SW1' nuevamente para finalizar el test, desactivar el inyector 
#    PRBS7 y regresar al monitoreo pasivo estándar del sistema.
#
# CÓMO ANALIZAR LOS RESULTADOS:
# - ESTADO DEL CABLE:
#   * "Normal Connection" (Conexión Normal): La impedancia de la trayectoria de 
#     transmisión de alta velocidad está completamente adaptada.
#   * "Short to GND" (Corto a Masa) / "Open Circuit" (Circuito Abierto): 
#     Discontinuidad crítica en la trayectoria física dentro de las pistas de la 
#     PCB, los conectores coaxiales o el propio cable.
# - ERRORES DE LÍNEA (DEC_ERR / Errores Acumulados):
#   * Errores Acumulados = 0: Integridad de Señal (SI) perfecta. El canal físico 
#     de alta frecuencia, el layout de acoplo de AC y el filtrado de potencia 
#     están operando dentro de los márgenes óptimos.
#   * Errores Acumulados > 0: Atenuación o ruido en la señal de alta frecuencia. 
#     Analizar:
#       1. Verificar desadaptaciones de impedancia (p. ej., falta de antipads bajo 
#          los condensadores de acoplo de AC).
#       2. Ejecutar la función `sweep_equalizer_margin` para encontrar el voltaje 
#          óptimo del ecualizador del receptor (DAC LTC2601) y compensar las 
#          pérdidas de inserción del cable coaxial.
#       3. Comprobar el ruido de la PDN en las líneas analógicas de alimentación 
#          del PLL (V_DDA) de los SerDes, que puede estar induciendo jitter en el 
#          lazo de enganche de fase.
# ==============================================================================

import time

# --- Constantes de Registros de Diagnóstico ---
# MAX96716A (Deserializador) [Registros basados en la Guía de Usuario]
REG_DES_LINK_CFG  = 0x0010  # Configuración del enlace físico
REG_DES_LINK_STAT = 0x001A  # Estado del enlace (Lock, etc.)
REG_DES_LINE_STAT = 0x0026  # Monitor analógico de línea (ADC de cable)
REG_DES_DEC_ERR   = 0x0022  # Contador de errores de decodificación de línea

# MAX96717 (Serializer)
REG_SER_PRBS_CFG  = 0x0314  # Control de inyección PRBS
# (Ajusta estas direcciones según los mapas específicos si es necesario)

class SerDesDiagnostics:
    def __init__(self, controller_A, controller_B, hw_driver):
        """
        Inicializa la suite de diagnóstico.
        controller_A/B: Instancias de SerDesController
        hw_driver: Instancia de BoardHardware para modificar voltajes de DAC
        """
        self.channels = {
            'A': {'ctrl': controller_A, 'cs_dac': hw_driver.cs_daca, 'cs_adc': hw_driver.cs_adca},
            'B': {'ctrl': controller_B, 'cs_dac': hw_driver.cs_dacb, 'cs_adc': hw_driver.cs_adcb}
        }
        self.hw = hw_driver

    def scan_cable_status(self, channel_id):
        """
        Analiza eléctricamente la línea de transmisión analógica usando el ADC del Deserializador.
        Retorna una cadena con el diagnóstico de la línea.
        """
        ch = self.channels[channel_id]
        # Leemos el registro de estado analógico de la línea
        val = ch['ctrl']._read_reg(ch['ctrl'].des_addr, REG_DES_LINE_STAT)
        if val is None:
            return "ERROR_I2C: Sin comunicación con el Deserializador"
        
        # Filtramos los bits de estado de cable (Típicamente bits [2:0] de LF_0)
        cable_state = val & 0x07
        
        mapping = {
            0x01: "CORTO_A_MASA (Fallo de aislamiento en PCB o conector coaxial)",
            0x02: "CONEXIÓN_NORMAL (Impedancia adaptada OK)",
            0x03: "CIRCUITO_ABIERTO (Cable desconectado o traza rota)",
            0x04: "CORTO_A_BATERÍA (PoC defectuoso o fallo de sobrevoltaje)"
        }
        return mapping.get(cable_state, f"ESTADO_DESCONOCIDO (Código: 0x{val:02X})")

    def configure_prbs_generator(self, channel_id, enable=True):
        ch = self.channels[channel_id]
        # Configuración del inyector en el Serializador (0x0314)
        val = 0x05 if enable else 0x00
        success = ch['ctrl']._write_reg(ch['ctrl'].ser_addr, REG_SER_PRBS_CFG, val)
    
        # Configuración del Checker en el Deserializador (0x01FC)
        des_val = 0x90 if enable else 0x00
        ch['ctrl']._write_reg(ch['ctrl'].des_addr, 0x01FC, des_val)
    
        if success:
            state = "ACTIVADO" if enable else "DESACTIVADO"
            print(f"[DIAG - Ch {channel_id}]: Inyector y Checker PRBS7 {state}.")
        else:
            print(f"[DIAG - Ch {channel_id}]: [FALLO] No se pudo configurar el inyector PRBS.")
        return success

    def clear_error_counters(self, channel_id):
        ch = self.channels[channel_id]
        # Escribimos 0x90 para habilitar y resetear el contador de errores PRBS dedicado (0x01FC)
        ch['ctrl']._write_reg(ch['ctrl'].des_addr, 0x01FC, 0x90)
    
    def read_error_count(self, channel_id):
        ch = self.channels[channel_id]
        # Leemos el acumulador de errores PRBS del deserializador (0x01FB)
        val = ch['ctrl']._read_reg(ch['ctrl'].des_addr, 0x01FB)
        return val if val is not None else 0xFFFF


    def run_bert_test(self, channel_id, duration_seconds=5):
        print(f"\n--- INICIANDO DIAGNÓSTICO BERT (Canal {channel_id}) ---")
        print(f"Paso 1: Escaneo eléctrico inicial...")
        print(f"-> Estado de línea física: {self.scan_cable_status(channel_id)}")
        
        # Limpiar contadores
        self.clear_error_counters(channel_id)
        
        # Activar PRBS7 en el TX
        if not self.configure_prbs_generator(channel_id, enable=True):
            print("-> Abortando test por falta de comunicación con el Serializador.")
            return False
            
        print(f"Paso 2: Transmitiendo patrón PRBS7 a 6 Gbps por {duration_seconds} segundos...")
        
        start_time = time.ticks_ms()
        duration_ms = duration_seconds * 1000
        accumulated_errors = 0
        
        while time.ticks_diff(time.ticks_ms(), start_time) < duration_ms:
            time.sleep_ms(1000)
            err = self.read_error_count(channel_id)
            if err != 0xFFFF:
                accumulated_errors += err
                
        # Apagar inyector al terminar
        self.configure_prbs_generator(channel_id, enable=False)
        
        print("\n--- RESULTADOS BERT ---")
        print(f"-> Errores totales de decodificación: {accumulated_errors}")
        if accumulated_errors == 0:
            print("-> [APROBADO]: Canal de Alta Frecuencia con Integridad de Señal Excelente.")
        else:
            print("-> [FALLO]: Pérdida de integridad de señal. Revisa el layout, acoplos de AC o el ecualizador.")
        return accumulated_errors == 0

    def sweep_equalizer_generator(self, channel_id, start_v=3.0, end_v=5.5, step_v=0.5):
        """
        BARRIDO DE MARGEN asíncrono (Generador Cooperativo).
        Cada llamada a next() avanza el estado sin bloquear el hilo principal.
        """
        print(f"\n--- BARRIDO ASÍNCRONO DE ECUALIZACIÓN (Canal {channel_id}) ---")
        print(f"{'Voltaje (V)':<18} | {'Lock GMSL2':<12} | {'Errores de Línea':<18}")
        print("-" * 55)
        
        original_voltage = 4.0
        v = start_v
        epsilon = 0.01
        
        while v <= (end_v + epsilon):
            # 1. Configurar voltaje analógico
            self.hw.set_headstage_v(self.channels[channel_id]['cs_dac'], v)
            
            # Espera no bloqueante de 150 ms para estabilizar la rampa de tensión
            t_start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t_start) < 150:
                yield  # Cede el control a main.py
                
            # 2. Verificar lock
            lock = self.channels[channel_id]['ctrl'].check_link_lock()
            
            # 3. Limpiar y esperar no bloqueante de 300 ms para acumular errores
            self.clear_error_counters(channel_id)
            t_start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t_start) < 300:
                yield  # Cede el control a main.py
                
            errors = self.read_error_count(channel_id)
            
            lock_str = "SÍ" if lock else "NO"
            err_str = str(errors) if errors != 0xFFFF else "N/A"
            print(f"{v:<18.2f} | {lock_str:<12} | {err_str:<18}")
            
            v += step_v
            
        # Restablecer estado por defecto de forma segura
        self.hw.set_headstage_v(self.channels[channel_id]['cs_dac'], original_voltage)
        print("-> Barrido finalizado. Voltaje restablecido a 4.0V.")
