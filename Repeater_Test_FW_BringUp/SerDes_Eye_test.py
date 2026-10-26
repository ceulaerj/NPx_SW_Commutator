# serdes_eye_test.py
# Módulo de diagnóstico avanzado de apertura de ojo y márgenes de señal GMSL2
# Target: NPNXT_RPTST_00 (Raspberry Pi Pico / RP2040) — MAX96716A + MAX96717

# ==============================================================================
# DIAGNÓSTICO DEL MARGEN DE ENLACE: INTERPRETACIÓN DE REG_RLMS_EOM_STAT (0x1407)
# ==============================================================================
# El registro de solo lectura 0x1407 (RLMS7) refleja el veredicto final de la
# capa física (PHY) del ecualizador adaptativo (AEQ) a 6 Gbps.
#
# ESTRUCTURA DE EXTRACCIÓN DE BITS:
# - Bit [7]: EOM_DONE -> Indica si la bomba de carga analógica terminó de 
#                        integrar las muestras de estrés configuradas.
# - Bits [6:0]: EOM   -> Magnitud escalar de la apertura vertical/horizontal.
#
# CÓMO ANALIZAR LOS VALORES LEÍDOS EN ENTORNO DE LABORATORIO:
# ------------------------------------------------------------------------------
# RANGO (Bits [6:0]) | ESTADO DE INTEGRIDAD (SI)  | COMPORTAMIENTO FÍSICO REAL
# ------------------------------------------------------------------------------
#  0x00 a 0x0F (0-15)  | CRÍTICO / OJO CERRADO      | Enlace propenso a bit errors.
#                      |                            | Pérdidas por inserción > -21.0dB 
#                      |                            | o stubs resonantes en los pads.
# ------------------------------------------------------------------------------
#  0x10 a 0x23 (16-35) | MARGEN DEGRADADO           | Link estable pero al límite.
#                      |                            | Jitter determinista inducido por 
#                      |                            | ruido de conmutación en la PDN.
# ------------------------------------------------------------------------------
#  0x24 a 0x46 (36-70) | OPERACIÓN CONFORME (OK)    | Margen normal para longitudes
#                      |                            | estándar de cables coaxiales de 50 Ohms.
# ------------------------------------------------------------------------------
#  0x47 a 0x7F (71-127)| EXCELENTE INTEGRIDAD       | Layout óptimo. Antipads correctos
#                      |                            | bajo los capacitores de acoplo AC.
# ==============================================================================

import machine
import time

def decodificar_registro_eom(stat_done_val, margin_val, canal):
    """
    Parsea el registro unificado 0x1407 (RLMS7) según las especificaciones de ADI/Maxim.
    Muestra la tabla comparativa de diagnóstico en la consola Thonny.
    """
    eom_done = (stat_done_val >> 7) & 0x01   # Bit [7] de 0x1407: EOM_DONE (Integración completa)
    eye_margin = margin_val & 0x7F           # Bits [6:0] de 0x1407: EOM (Magnitud de apertura)
    
    print("\n" + "-"*65)
    print(f" 📊 TELEMETRÍA DE HARDWARE RECEPTOR [{canal}]: MAX96716A EOM PHY STATUS (0x1407)")
    print("-"*65)
    print(f" Estado de Integración (Bit 7 - EOM_DONE) : {eom_done} -> " + 
          ("CONCLUIDO (Datos Válidos)" if eom_done else "PROCESANDO..."))
    print(f" Magnitud de Apertura (Bits [6:0] - EOM) : {eye_margin} unidades")
    print("-"*65)
    
    # Evaluación paramétrica de microondas a 3 Gbps / 6 Gbps
    if eye_margin <= 5:
        estado_si = "🚨 CRÍTICO (Ojo cerrado / Alta tasa de errores BER)"
        accion = "Comprobar Return Loss, cortocircuitos o falta de antipads en la PCB."
    elif eye_margin < 15:
        estado_si = "⚠️ MARGINAL / DEGRADADO (Ojo Cerrado en PHY - Rango Inseguro)"
        accion = "Revisar ecualización CTLE o ruido transitorio en la PDN."
    elif eye_margin <= 35:
        estado_si = "✅ CONFORME (Operación Normal / Buen colchón de fase)"
        accion = "Comportamiento excelente para cable coaxial."
    else:
        estado_si = "💎 EXCELENTE (Layout de microondas impecable)"
        accion = "Canal perfectamente adaptado a 50 Ohms."
        
    print(f" Diagnóstico SI: {estado_si}")
    print(f" Acción técnica: {accion}")
    print("-"*65 + "\n")
    
    return eom_done, eye_margin

def ejecutar_eye_mapping(i2c, des_addr, canal):
    """
    Ejecuta el diagnóstico del Eye-Opening Monitor (EOM) real en GMSL2.
    Interroga al bloque RLMS del silicio de GHz usando el registro unificado 0x1407.
    """
    print(f"\n[{canal}] Inicializando telemetría física del ojo (Silicio EOM GMSL2 - 0x1407)...")
    
    REG_RLMS_EOM_CFG  = 0x1404  # Configuración EOM
    REG_RLMS_EOM_STAT = 0x1407  # Registro unificado RLMS7 (Bit 7 = EOM_DONE, Bits [6:0] = EOM)
    
    def _write_reg_16bit_addr(reg, val):
        buf = bytearray([(reg >> 8) & 0xFF, reg & 0xFF, val & 0xFF])
        i2c.writeto(des_addr, buf)

    def _read_reg_16bit_addr(reg):
        reg_buf = bytearray([(reg >> 8) & 0xFF, reg & 0xFF])
        i2c.writeto(des_addr, reg_buf)
        time.sleep_ms(2)
        return i2c.readfrom(des_addr, 1)[0]

    try:
        # Verificar que haya LOCK real en vivo (Bit 2 de 0x0013)
        stat_13 = _read_reg_16bit_addr(0x0013)
        if stat_13 is None or not bool(stat_13 & 0x04):
            print("⚠️ [ERROR EOM]: No hay LOCK de capa física (Cable desconectado o sin portadora).")
            decodificar_registro_eom(0x00, 0x00, canal)
            # RENDERIZADO FORZADO DE OJO CERRADO SI NO HAY LOCK
            print("="*45)
            print(f"    DIAGRAMA DE ENLACE ANALÓGICO - CANAL RECEPTOR {canal}")
            print("="*45)
            for _ in range(11):
                print("    | ################################ |")
            print("    " + "-"*43)
            print("    + Margen EOM PHY: 0 u. [🚨 OJO CERRADO / Sin Lock]")
            print("="*45)
            return

        # 1. Limpiar/Resetear el estado previo del EOM antes de iniciar la medición
        _write_reg_16bit_addr(REG_RLMS_EOM_CFG, 0x00)
        time.sleep_ms(20)

        # 2. Habilitar el monitor de ojo en chip (EOM_EN)
        _write_reg_16bit_addr(REG_RLMS_EOM_CFG, 0x4D)
        
        print(f"[{canal}] Integrando muestras de GHz en el ecualizador adaptativo...")
        
        # 3. Polling activo en 0x1407 hasta que EOM_DONE (Bit 7) sea 1 (Timeout 1.5s)
        timeout_ms = 1500
        t_start = time.ticks_ms()
        val_1407 = 0
        
        while time.ticks_diff(time.ticks_ms(), t_start) < timeout_ms:
            val_1407 = _read_reg_16bit_addr(REG_RLMS_EOM_STAT)
            if val_1407 is not None and (val_1407 & 0x80) != 0:
                break
            time.sleep_ms(50)
            
        if val_1407 is None:
            val_1407 = 0x00

        # 4. Decodificación paramétrica unificada
        eom_done, eye_margin = decodificar_registro_eom(val_1407, val_1407, canal)
        
        # 5. Render ASCII dinámico y fiel a la apertura real
        print("="*45)
        print(f"    DIAGRAMA DE ENLACE ANALÓGICO - CANAL RECEPTOR {canal}")
        print("="*45)
        
        # REGLA DE CAPA FÍSICA: Si el margen es menor a 15 unidades, el ojo está CERRADO (apertura = 0)
        if eye_margin < 15:
            apertura_central = 0
        else:
            apertura_central = int((eye_margin / 127.0) * 16)
            
        for fila in range(11):
            distancia_centro = abs(5 - fila)
            if apertura_central > 0:
                expansion_fila = max(0, apertura_central - (distancia_centro * int(apertura_central / 5)))
            else:
                expansion_fila = 0
            
            espacios_izq = 16 - expansion_fila
            
            borde_izq = "#" * espacios_izq
            ojo_centro = " " * (expansion_fila * 2)
            borde_der = "#" * espacios_izq
            
            print(f"    | {borde_izq}{ojo_centro}{borde_der} |")
                
        print("    " + "-"*43)
        if eye_margin < 15:
            print(f"    + Margen EOM PHY: {eye_margin} u. [🚨 OJO CERRADO (< 15 u)]")
        else:
            print(f"    + Margen de Apertura (EOM PHY Status): {eye_margin} unidades lógicas.")
        print("="*45)
        
        # 6. TABLA DE INTERPRETACIÓN RÁPIDA DE RESULTADOS
        print("\n  📋 GUÍA DE INTERPRETACIÓN RÁPIDA EOM:")
        print("  ┌───────────────┬──────────────────────┬──────────────────────────────────┐")
        print("  │ Valor EOM     │ Estado del Enlace    │ Diagnóstico Operativo            │")
        print("  ├───────────────┼──────────────────────┼──────────────────────────────────┤")
        print("  │ 0             │ Sin Enlace / Cerrado │ Cable atenuado / Desconectado    │")
        print("  │ 1 a 14        │ Margen Crítico       │ Ojo Cerrado / Bit errors         │")
        print("  │ 15 a 35       │ Margen Acceptable    │ Operación funcional con riesgo   │")
        print("  │ 36 a 127      │ Margen Excelente     │ Enlace robusto sin errores BER=0 │")
        print("  └───────────────┴──────────────────────┴──────────────────────────────────┘\n")

    except OSError:
        print(f"⚠️ [ERROR I2C CRÍTICO]: Sin respuesta del Deserializador del Canal {canal} en 0x{des_addr:02X}.")