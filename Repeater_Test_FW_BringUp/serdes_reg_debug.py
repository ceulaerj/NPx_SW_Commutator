# ==============================================================================
# 📖 GUÍA RÁPIDA DE INICIO EN LA CONSOLA (REPL) DE THONNY (CANAL A o B)
# ==============================================================================
# Para usar este depurador de registros en caliente sin alterar su main.py:
#
# 1. Ejecute "main.py" presionando el botón verde de Thonny para encender la placa.
# 2. Haga clic en la pestaña "Shell" (Consola) inferior de Thonny.
# 3. Presione "Ctrl + C" en el teclado para detener el lazo pero mantener la RAM viva.
# 4. Copie, pegue estas líneas en la consola según el canal y presione Enter:
#
#   OPCIÓN A) PARA EL CANAL A (I2C0):
#      from serdes_reg_debug import GMSLRegisterDebugger
#      dbg = GMSLRegisterDebugger(i2c0_A)
#      dbg.help()
#
#   OPCIÓN B) PARA EL CANAL B (I2C1):
#      from serdes_reg_debug import GMSLRegisterDebugger
#      dbg = GMSLRegisterDebugger(i2c1_B)
#      dbg.help()
#
#  OPCIÓN C) USO DE BREAKPOINTS INTERACTIVOS POR SOFTWARE (DENTRO DE main.py):
#     Si desea detener temporalmente su script 'main.py' en un punto específico
#     de la secuencia de arranque (por ejemplo, después de estabilizar los LDOs)
#     para inspeccionar o modificar registros SerDes en caliente, y luego continuar 
#     con el programa principal, siga estos pasos:
#
#     1. Importe el módulo e instancie el depurador al final de 'main.py':
#        from serdes_reg_debug import GMSLRegisterDebugger
#        dbg_A = GMSLRegisterDebugger(i2c0_A)
#
#     2. Inserte la llamada del breakpoint interactivo donde desee pausar la placa:
#        dbg_A.stop_debug("LDO Canal A configurado a 4.0V")
#
#     3. Al ejecutar 'main.py', Thonny se pausará en esa línea abriendo el prompt:
#        GMSL_STOP_DEBUG >>>
#
#     4. Escriba sus comandos de lectura/escritura (ej: dump d 0x0010 10). Al terminar,
#        ingrese 'q' o 'c' para liberar el breakpoint y continuar con 'main.py'.
#
# ==============================================================================

# serdes_reg_debug.py
# Módulo de exploración, volcado y depuración interactiva de registros de 16 bits para GMSL2
# Compatible con NPNXT_RPTST_00 (Raspberry Pi Pico / RP2040)

import machine
import time

class GMSLRegisterDebugger:
    def __init__(self, i2c_bus, des_addr=0x6A, ser_addr=0x40, canal=None):
        """
        des_addr: Dirección I2C de 7 bits del Deserializador (0xD4 >> 1)
        ser_addr: Dirección I2C de 7 bits del Serializador (0x80 >> 1)
        canal: Fuerza de manera manual la etiqueta del canal ('A' o 'B')
        """
        self.i2c = i2c_bus
        self.des_addr = des_addr
        self.ser_addr = ser_addr
        
        # Detección automática estricta del canal según el ID del bus físico si no se especifica [cite: 1.1.2]
        if canal is not None:
            self.canal = str(canal).upper()
        else:
            bus_str = str(i2c_bus).replace(" ", "")
            # Buscamos de forma estricta "I2C(0" para evitar falsos positivos con los ceros de "freq=100000"
            self.canal = "A" if "I2C(0" in bus_str else "B"
        
    def help(self):
        """
        Muestra la guía rápida de comandos interactivos para Thonny directamente en la consola.
        """
        print("\n" + "="*65)
        print(f" 📖 GUÍA RÁPIDA DE USO INTERACTIVO: GMSLRegisterDebugger [Canal {self.canal}]")
        print("="*65)
        print(" Instanciación según el canal físico bajo prueba:")
        print("  - Para Canal A (I2C0): dbg = GMSLRegisterDebugger(i2c0_A)")
        print("  - Para Canal B (I2C1): dbg = GMSLRegisterDebugger(i2c1_B)")
        print(f"\n Instancia activa actual : CANAL {self.canal}")
        print("\n 1. LECTURA FORMATEADA (Muestra Hexadecimal y Binario):")
        print(f"    dbg.print_reg(\"Deserializador\", 0x6A, 0x0010)")
        print("\n 2. ESCRITURA EN CALIENTE (Escribe un byte en registro de 16-bits):")
        print("    dbg.write_reg(0x6A, 0x0011, 0x05)")
        print("\n 3. VOLCADO CONTINUO DE REGISTROS (Hex Dump de N registros):")
        print("    dbg.dump_registers(\"Deserializador\", 0x6A, 0x0010, 10)")
        print("\n 4. MODIFICACIÓN INDIVIDUAL DE BITS (Read-Modify-Write):")
        print("    dbg.modify_bit(\"Deserializador\", 0x6A, 0x0001, bit_pos, valor)")
        print("    - bit_pos: Rango 0 (LSB) a 7 (MSB)")
        print("    - valor  : 0 o 1")
        print("\n 5. VERIFICACIÓN DE STRAPPING FÍSICO (CFG0 / CFG1):")
        print("    dbg.verificar_bootstrap_cfg()")
        print("\n Direcciones de referencia en MicroPython (7-bit) comunes a ambos canales:")
        print("  - Deserializador (MAX96716A): 0x6A (8-bit: 0xD4)")
        print("  - Serializador (MAX96717)  : 0x40 (8-bit: 0x80)")
        print("="*65 + "\n")

    def stop_debug(self, label=""):
        """
        Punto de interrupción por software con volcado automático y pausa por botón.
        Imprime el estado de los registros clave del SerDes de forma autónoma
        y pausa la Pico de forma estable hasta presionar el botón físico SW1 de la placa.
        """
        print("\n" + "="*65)
        if label:
            print(f" ⏸️  BREAKPOINT INTERACTIVO [{label}] - CANAL {self.canal}")
        else:
            print(f" ⏸️  BREAKPOINT INTERACTIVO - CANAL {self.canal}")
        print("="*65)
        print(" El programa principal se ha PAUSADO de forma segura.")
        print(f" Realizando volcado automático de registros clave del Canal {self.canal}:")
        
        # 1. Mostrar de forma automática el estado del enlace y del decodificador
        self.print_reg("Deserializador", self.des_addr, 0x0010) # Estado de Link Cfg
        self.print_reg("Deserializador", self.des_addr, 0x0013) # Estado de LOCK / PLL
        self.print_reg("Deserializador", self.des_addr, 0x001A) # Estado de Link Stat
        self.print_reg("Deserializador", self.des_addr, 0x0022) # Contador de errores DEC
        self.print_reg("Serializador  ", self.ser_addr, 0x0001) # Forward Rate del Tx
        
        print("\n 🔌 Presione el botón físico SW1 de la placa para reanudar main.py...")
        print("="*65 + "\n")
        
        # Pin del pulsador SW1 (GP28) configurado con Pull-Up interno
        btn_sw1 = machine.Pin(28, machine.Pin.IN, machine.Pin.PULL_UP)
        
        # 2. Bucle de espera físico completamente inmune a fallos serie de Thonny
        while btn_sw1.value() == 1:
            time.sleep_ms(10)
            
        # Pequeño retardo antirrebote antes de reanudar el flujo principal
        time.sleep_ms(200)
        print(f"[DEBUG]: Botón SW1 presionado. Reanudando ejecución principal...\n")

    def verificar_bootstrap_cfg(self):
        """
        Interroga y decodifica las configuraciones físicas de strapping (CFG0 y CFG1)
        latcheadas por el hardware del Deserializador y el Serializador durante el arranque.
        Permite validar de forma analítica si las resistencias físicas de la PCB son correctas.
        """
        print("\n" + "="*65)
        print(f" 🔍 REPORTE DE STRAPPING DE HARDWARE (CFG0 / CFG1) - CANAL {self.canal}")
        print("="*65)
        
        # --- DESERIALIZADOR (0xD4 / 0x6A) ---
        print(f" ─── DESERIALIZADOR {self.canal} (Dirección física: 0xD4) ───")
        addr_des = self.des_addr
        
        # Leer registro 0x0000 (I2C address latcheada por CFG0) [cite: 1.1.3]
        r0 = self.read_reg(addr_des, 0x0000)
        # Leer registro 0x0001 (Velocidad latcheada por CFG1) [cite: 2.3.1]
        r1 = self.read_reg(addr_des, 0x0001)
        # Leer registro 0x0011 (Tipo de cable latcheado por CFG1) [cite: 2.3.1]
        r11 = self.read_reg(addr_des, 0x0011)
        
        if r0 is not None and r1 is not None and r11 is not None:
            # Decodificar Dirección I2C (CFG0)
            print(f"  • I2C Base Address (CFG0)   : 0x{r0:02X} -> " + 
                  ("0xD4 (I2C Sel)" if r0 == 0xD4 else f"Personalizada (0x{r0:02X})"))
            
            # Decodificar Cable Type (CFG1 - CXTP) [cite: 2.3.1]
            cxtp = r11 & 0x01
            print(f"  • Cable Physical Type (CFG1): " + 
                  ("COAXIAL (Cx)" if cxtp == 1 else "Shielded Twisted Pair (STP)"))
            
            # Decodificar Speed (CFG1 - RX_RATE) [cite: 2.3.1]
            rx_rate = r1 & 0x03
            rate_str = "6 Gbps" if rx_rate == 2 else "3 Gbps" if rx_rate == 1 else f"Reservado (bits: {rx_rate:02b})"
            print(f"  • Link Data Rate (CFG1)     : {rate_str}")
        else:
            print(f"  ❌ [ERROR]: No hay comunicación con el Deserializador {self.canal} (verifique energía/coaxial)")
            
        print(f"\n ─── SERIALIZADOR {self.canal} (Dirección física: 0x80) ───")
        addr_ser = self.ser_addr
        
        # Leer registro 0x0000 (I2C address latcheada por CFG0) [cite: 1.2.2]
        s0 = self.read_reg(addr_ser, 0x0000)
        # Leer registro 0x0001 (Forward Rate latcheada por CFG1) [cite: 1.4.3]
        s1 = self.read_reg(addr_ser, 0x0001)
        # Leer registro 0x0011 (Cable Type latcheado por CFG1)
        s11 = self.read_reg(addr_ser, 0x0011)
        
        if s0 is not None and s1 is not None and s11 is not None:
            # Decodificar Dirección I2C (CFG0) [cite: 1.2.2]
            print(f"  • I2C Base Address (CFG0)   : 0x{s0:02X} -> " + 
                  ("0x80 (I2C Sel)" if s0 == 0x80 else f"Personalizada (0x{s0:02X})"))
            
            # Decodificar Cable Type (CFG1)
            cxtp_ser = s11 & 0x01
            print(f"  • Cable Physical Type (CFG1): " + 
                  ("COAXIAL (Cx)" if cxtp_ser == 1 else "Shielded Twisted Pair (STP)"))
            
            # Decodificar Speed (CFG1 - Forward Rate)
            tx_rate = (s1 >> 2) & 0x03
            rate_ser_str = "6 Gbps" if tx_rate == 2 else "3 Gbps" if tx_rate == 1 else f"Reservado (bits: {tx_rate:02b})"
            print(f"  • Link Data Rate (CFG1)     : {rate_ser_str}")
        else:
            print(f"  ❌ [ERROR]: No hay comunicación con el Serializador {self.canal} (verifique link LOCK / retorno)")
            
        print("="*65 + "\n")
        
    def read_reg(self, dev_addr, reg):
        """Lee un registro de 16 bits y retorna su valor (0x00 - 0xFF)."""
        reg_buf = bytearray([(reg >> 8) & 0xFF, reg & 0xFF])
        try:
            # Eliminamos el parámetro "False" para usar STOP completo
            self.i2c.writeto(dev_addr, reg_buf)
            time.sleep_ms(2)
            res = self.i2c.readfrom(dev_addr, 1)
            return res[0]
        except OSError:
            return None
            
    def write_reg(self, dev_addr, reg, val):
        """Escribe un byte en un registro de 16 bits usando direccionamiento de 16 bits."""
        buf = bytearray([(reg >> 8) & 0xFF, reg & 0xFF, val & 0xFF])
        try:
            self.i2c.writeto(dev_addr, buf)
            return True
        except OSError:
            return False
            
    def print_reg(self, dev_name, dev_addr, reg):
        """Muestra de forma formateada el valor de un registro con su representación binaria."""
        val = self.read_reg(dev_addr, reg)
        if val is not None:
            bin_str = f"{val:08b}"
            bin_formatted = bin_str[:4] + " " + bin_str[4:]
            print(f"[{dev_name} {self.canal} (0x{dev_addr:02X})] Reg 0x{reg:04X} = 0x{val:02X} | bin: {bin_formatted}")
        else:
            print(f"❌ [{dev_name} {self.canal} (0x{dev_addr:02X})] Reg 0x{reg:04X} -> Error de comunicación (NACK)")
            
    def modify_bit(self, dev_name, dev_addr, reg, bit, value):
        """
        Realiza una lectura-modificación-escritura (RMW) en un bit específico (0-7).
        value: 0 o 1
        """
        if bit < 0 or bit > 7:
            print("❌ Error: El bit debe estar en el rango de 0 a 7.")
            return False
            
        val = self.read_reg(dev_addr, reg)
        if val is None:
            print(f"❌ [RMW FAIL]: No se pudo leer el registro 0x{reg:04X} para modificar.")
            return False
            
        if value == 1:
            new_val = val | (1 << bit)
        else:
            new_val = val & ~(1 << bit)
            
        success = self.write_reg(dev_addr, reg, new_val)
        if success:
            print(f"🛠️ [RMW OK] {dev_name} {self.canal} 0x{reg:04X}: 0x{val:02X} -> 0x{new_val:02X} (Bit {bit} cambiado a {value})")
            return True
        else:
            print(f"❌ [RMW FAIL]: Fallo de escritura en 0x{reg:04X}")
            return False

    def dump_registers(self, dev_name, dev_addr, start_reg, count):
        """
        Realiza un volcado (hex dump) continuo de un bloque de registros.
        """
        print(f"\n--- VOLCADO DE REGISTROS: {dev_name} {self.canal} (0x{dev_addr:02X}) ---")
        print(f"{'Registro':<10} | {'Hex':<6} | {'Binario':<10}")
        print("-" * 35)
        
        for offset in range(count):
            reg = start_reg + offset
            val = self.read_reg(dev_addr, reg)
            if val is not None:
                bin_str = f"{val:08b}"
                bin_formatted = bin_str[:4] + " " + bin_str[4:]
                print(f"0x{reg:04X}     | 0x{val:02X} | {bin_formatted}")
            else:
                print(f"0x{reg:04X}     | NACK | --")
        print("-" * 35 + "\n")