# board_hw.py
# Abstracción de hardware para NPNXT_RPTST_00 (Raspberry Pi Pico / RP2040)
# Buses I2C/SPI/GPIO de la MCU se configuran en main.py
import machine
import time

# --- MCP23S08 Physical Hardware Addresses (Page 6) ---
ADDR_U3  = 0x40  # Local expander U3 (LEDs, DAC HSA, Control Channel A)
ADDR_U31 = 0x42  # Local expander U31 (Control and status lines Channel B)
ADDR_U32 = 0x44  # Local expander U32 (Power enables for LDOs and global PWDNs)
IODIR, GPIO, IOCON = 0x00, 0x09, 0x05

# --- INA239 Internal Register Map (Pages 7 & 8) ---
INA239_CONFIG_REG = 0x00
INA239_SHNT_CAL   = 0x02
INA239_VBUS_REG   = 0x05
INA239_CURRENT_REG = 0x07

class BoardHardware:
    def __init__(self, spi_bus, csi_spi, cs_daca, cs_dacb, cs_adca, cs_adcb, r_shunt=0.200):
        """
        r_shunt: Resistencia del shunt física en Ohms (por defecto 200 mOhm o 0.200)
        """
        self.spi = spi_bus
        self.csi_spi = csi_spi
        self.cs_daca = cs_daca
        self.cs_dacb = cs_dacb
        self.cs_adca = cs_adca
        self.cs_adcb = cs_adcb
        
        # Parametrización física de la escala del INA239
        self.r_shunt = r_shunt
        # Ecuación física INA239 con SHNT_CAL = 8192 (0x2000):
        # Current_LSB = 10^-5 / R_shunt
        self.current_lsb = 1e-5 / self.r_shunt

    def mcp_global_init(self):
        print("[CRITICAL]: Esperando estabilización de tensiones analógicas...")
        time.sleep_ms(50)  # Filtro analógico temporal para el encendido del plano de masa/LDOs

        print("[CRITICAL]: Habilitando HAEN global mediante broadcast...")
        self.csi_spi.value(0)
        # Escribe 0x08 al registro IOCON de la dirección base global (0x40)
        self.spi.write(bytearray([0x40, IOCON, 0x08])) 
        self.csi_spi.value(1)
        time.sleep_ms(15)

        # Validación individual por reintento direccionado
        expansores = [ADDR_U3, ADDR_U31, ADDR_U32]
        for addr in expansores:
            val = self.mcp_read(addr, IOCON)
            if val != 0x08:
                print(f"[RETRY]: Expander {hex(addr)} no respondió al broadcast. Forzando registro...")
                # Escribe de manera forzada al dispositivo físico persistiendo en su dirección específica
                self.mcp_write(addr, IOCON, 0x08)
                time.sleep_ms(5)
                # Segunda comprobación
                val_retry = self.mcp_read(addr, IOCON)
                if val_retry != 0x08:
                    print(f"[CRITICAL FAILURE]: Expander {hex(addr)} inaccesible o hardware defectuoso.")
                else:
                    print(f"[OK]: Expander {hex(addr)} enlazado y HAEN activo.")
            else:
                print(f"[OK]: Expander {hex(addr)} configurado con éxito.")
                
    def mcp_write(self, device_addr, register, value):
        self.csi_spi.value(0)
        self.spi.write(bytearray([device_addr, register, value]))
        self.csi_spi.value(1)

    def mcp_read(self, device_addr, register):
        self.csi_spi.value(0)
        self.spi.write(bytearray([device_addr | 0x01, register]))
        rx = self.spi.read(1)
        self.csi_spi.value(1)
        return rx[0]

    def setup_expanders(self):
        print("[INFO]: Forzando estado seguro inicial (Limpieza de GPIOs)...")
        # 1. Colocamos todas las salidas lógicas en un estado seguro e inactivo (LOW / 0x00)
        # Esto apaga los LEDs de test, limpia los habilitadores de potencia y pone los interruptores en Modo Interno.
        self.mcp_write(ADDR_U3, GPIO, 0x0F) # LEDs off y Clear DAC high
        self.mcp_write(ADDR_U31, GPIO, 0x10)
        self.mcp_write(ADDR_U32, GPIO, 0x00)

        print("[INFO]: Configuring IODIRs...")
        self.mcp_write(ADDR_U3, IODIR, 0xC0)      # Configures U3
        self.mcp_write(ADDR_U31, IODIR, 0xE4)     # Configures U31
        self.mcp_write(ADDR_U32, IODIR, 0x03)     # Configures U32

    def power_on_channel_A(self, monitor_pin):
        print("\n[POWER]: Activating Channel A LDO...")
        # 1. Encender LDO primero (Bit 6 de U32)
        current_u32 = self.mcp_read(ADDR_U32, GPIO)
        self.mcp_write(ADDR_U32, GPIO, current_u32 | 0x40) 
        
        # 2. Ahora esperar a que el hardware indique POWER GOOD
        timeout = 100
        while monitor_pin.value() == 0 and timeout > 0: 
            time.sleep_ms(1)
            timeout -= 1
        
        if monitor_pin.value() == 0:
            print("[CRITICAL ERROR]: Channel A LDO failed to reach Power Good.")
            return False
        
        print("[POWER]: Rail stable. Releasing PWDNB Reset...")
        # 3. Liberar Reset (PWDNB) de los chips (Bits 2 y 3 de U32)
        # Re-leemos para asegurar que el bit 6 (LDO) sigue activo
        current_u32 = self.mcp_read(ADDR_U32, GPIO)
        self.mcp_write(ADDR_U32, GPIO, current_u32 | 0x0C)
        
        # Retardo de estabilización para que el motor I2C del MAX96716A despierte
        time.sleep_ms(50) 
        return True

    def power_on_channel_B(self, monitor_pin):
        print("\n[POWER]: Activating Channel B LDO...")
        # 1. Encender LDO en U31 (Bit 3)
        current_u31 = self.mcp_read(ADDR_U31, GPIO)
        self.mcp_write(ADDR_U31, GPIO, current_u31 | 0x08)
        
        # 2. Esperar Power Good
        timeout = 100
        while monitor_pin.value() == 0 and timeout > 0:
            time.sleep_ms(1)
            timeout -= 1
            
        if monitor_pin.value() == 0:
            print("[CRITICAL ERROR]: Channel B LDO failed to reach Power Good.")
            return False
        
        print("[POWER]: Rail stable. Releasing PWDNB Reset...")
        # 3. Liberar Reset en U32 (Bits 4 y 5) para el Canal B
        current_u32 = self.mcp_read(ADDR_U32, GPIO)
        self.mcp_write(ADDR_U32, GPIO, current_u32 | 0x30)
        
        time.sleep_ms(50)
        return True
    
    def set_headstage_v(self, device_cs, real_voltage):
        if real_voltage < 2.72: real_voltage = 2.72 # Analytical hardware limits
        elif real_voltage > 5.98: real_voltage = 5.98
        v_ctrl = (5.98 - real_voltage) / 1.304 # Control transfer function
        dac_code = int((v_ctrl / 2.5) * 65535)
        dac_code = max(0, min(65535, dac_code)) # Garantiza rango de 16 bits
        # 3-byte (24-bit) SPI packet for LTC2601CDD
        spi_packet = bytearray([0x30, (dac_code >> 8) & 0xFF, dac_code & 0xFF])
        device_cs.value(0)
        time.sleep_us(2)
        self.spi.write(spi_packet)
        time.sleep_us(2)
        device_cs.value(1)

    def _spi_mode_ina239(self):
        """Conmuta el SPI0 al Modo 1 (CPOL=0, CPHA=1) a 1 MHz de forma segura."""
        self.spi.init(baudrate=1000000, polarity=0, phase=1)

    def _spi_mode_default(self):
        """Devuelve el SPI0 al Modo 0 (CPOL=0, CPHA=0) a 1 MHz."""
        self.spi.init(baudrate=1000000, polarity=0, phase=0)

    def cs_write_ina(self, device_cs, reg_addr, value_16bit):
        tx_buf = bytearray([(reg_addr << 2) & 0xFC, (value_16bit >> 8) & 0xFF, value_16bit & 0xFF])
        self._spi_mode_ina239()
        try:
            device_cs.value(0)
            time.sleep_us(2)
            self.spi.write(tx_buf)
            time.sleep_us(2)
            device_cs.value(1)
        finally:
            self._spi_mode_default() # Restauración garantizada ante excepciones

    def read_telemetry(self, device_cs):
        self._spi_mode_ina239()
        try:
            # Lectura de VBUS
            device_cs.value(0)
            time.sleep_us(2)
            self.spi.write(bytearray([(INA239_VBUS_REG << 2) | 0x01]))
            rx_v = self.spi.read(2)
            time.sleep_us(2)
            device_cs.value(1)
            
            # Lectura de Corriente
            device_cs.value(0)
            time.sleep_us(2)
            self.spi.write(bytearray([(INA239_CURRENT_REG << 2) | 0x01]))
            rx_i = self.spi.read(2)
            time.sleep_us(2)
            device_cs.value(1)
        finally:
            self._spi_mode_default() # Retorno de bus garantizado
        
        raw_v = (rx_v[0] << 8) | rx_v[1]
        v_real = raw_v * 0.003125 # Voltios

        raw_i = (rx_i[0] << 8) | rx_i[1]
        if raw_i & 0x8000: raw_i -= 0x10000
        
        # Conversión matemática estricta a miliamperios (mA)
        i_real = (raw_i * self.current_lsb) * 1000.0
        
        # Volts * mA = miliwatts (mW)
        pwr = v_real * i_real
        return v_real, i_real, pwr

    def ina239_configure(self, device_cs, name):
        self.cs_write_ina(device_cs, INA239_CONFIG_REG, 0x26CF)
        self.cs_write_ina(device_cs, INA239_SHNT_CAL, 0x2000)
        print("-> INA239 " + name + " Calibrated.")
   
    # --- FUNCIONES DE CONTROL PARA EL ISOLATED SWITCH (SW1) ---

    def set_channel_A_power_source(self, external=False):
        """
        Configura la fuente de alimentacion para el Canal A (VDD_HS_A).
        external=False -> Conmuta a VDD_HS_INT_A (LDO local) [Default -> Bit GP5 = 1 (HIGH)]
        external=True  -> Conmuta a VDD_HS_EXT_A (Remota QBSC) [Bit GP5 = 0 (LOW - Contacto NC)]
        Gobernado por el pin GP5 en U3 (Mascara de bit: 0x20)
        """
        current_u3 = self.mcp_read(ADDR_U3, GPIO)
        if external:
            # Ponemos a 0 el bit GP5 -> Relé desenergizado -> Contacto NC cerrado -> VDD_HS_EXT_A
            self.mcp_write(ADDR_U3, GPIO, current_u3 & ~0x20)
            print("[SWITCH]: Canal A conmutado a alimentacion EXTERNA (QBSC).")
        else:
            # Ponemos a 1 el bit GP5 -> Relé energizado -> Contacto NO cerrado -> VDD_HS_INT_A
            self.mcp_write(ADDR_U3, GPIO, current_u3 | 0x20)
            print("[SWITCH]: Canal A conmutado a alimentacion INTERNA (LDO Local).")

    def set_channel_B_power_source(self, external=False):
        """
        Configura la fuente de alimentacion para el Canal B (VDD_HS_B).
        external=False -> Conmuta a VDD_HS_INT_B (LDO local) [Default -> Bit GP1 = 1 (HIGH)]
        external=True  -> Conmuta a VDD_HS_EXT_B (Remota QBSC) [Bit GP1 = 0 (LOW - Contacto NC)]
        Gobernado por el pin GP1 en U31 (Mascara de bit: 0x02)
        """
        current_u31 = self.mcp_read(ADDR_U31, GPIO)
        if external:
            # Ponemos a 0 el bit GP1 -> Relé desenergizado -> Contacto NC cerrado -> VDD_HS_EXT_B
            self.mcp_write(ADDR_U31, GPIO, current_u31 & ~0x02)
            print("[SWITCH]: Canal B conmutado a alimentacion EXTERNA (QBSC).")
        else:
            # Ponemos a 1 el bit GP1 -> Relé energizado -> Contacto NO cerrado -> VDD_HS_INT_B
            self.mcp_write(ADDR_U31, GPIO, current_u31 | 0x02)
            print("[SWITCH]: Canal B conmutado a alimentacion INTERNA (LDO Local).")

    # --- RUTINAS UNIFICADAS PARA LA EEPROM M24128 (Canal A o B) ---

    def _get_eeprom_config(self, i2c0_A, i2c1_B, channel):
        """
        Metodo interno para resolver de forma dinamica el bus y la direccion 
        I2C segun el canal fisico indicado ('A' o 'B').
        """
        ch = str(channel).upper()
        if ch == 'A':
            return i2c0_A, 0x50  # EEPROM A: Bus i2c0_A, Dir 0x50
        elif ch == 'B':
            return i2c1_B, 0x51  # EEPROM B: Bus i2c1_B, Dir 0x51
        else:
            raise ValueError("[ERROR]: El canal debe ser 'A' o 'B'")

    def eeprom_write_byte(self, i2c0_A, i2c1_B, channel, mem_addr, data_byte):
        """
        Escribe un único byte en la EEPROM M24128 del canal especificado ('A' o 'B')
        usando el método nativo writeto_mem de MicroPython con dirección de 16 bits.
        """
        bus, dev_addr = self._get_eeprom_config(i2c0_A, i2c1_B, channel)
        try:
            # Escribir de forma nativa a dirección de memoria de 16 bits [cite: 1.1.2]
            bus.writeto_mem(dev_addr, mem_addr, bytes([data_byte]), addrsize=16)
            # Retardo de seguridad extendido para asegurar el ciclo de grabado físico (t_WR max es 10ms) [cite: 1.1.2]
            time.sleep_ms(20) 
            return True
        except OSError:
            print(f"[ERROR]: Fallo al escribir en EEPROM Canal {channel} ({hex(dev_addr)}) en {hex(mem_addr)}")
            return False

    def eeprom_read_byte(self, i2c0_A, i2c1_B, channel, mem_addr):
        """
        Lee un único byte de la EEPROM M24128 del canal especificado ('A' o 'B')
        usando el método nativo readfrom_mem (con Repeated Start) para evitar colisiones.
        """
        bus, dev_addr = self._get_eeprom_config(i2c0_A, i2c1_B, channel)
        try:
            # Leer de forma nativa usando Repeated Start (addrsize=16) [cite: 1.1.2]
            data = bus.readfrom_mem(dev_addr, mem_addr, 1, addrsize=16)
            return data[0]
        except OSError:
            print(f"[ERROR]: Fallo al leer de EEPROM Canal {channel} ({hex(dev_addr)}) en {hex(mem_addr)}")
            return None

    def eeprom_read_block(self, i2c0_A, i2c1_B, channel, start_mem_addr, length):
        """
        Lee un bloque continuo de bytes (lectura secuencial) del canal especificado ('A' o 'B').
        Ideal para leer strings completas como números de serie o IDs de imec.
        """
        bus, dev_addr = self._get_eeprom_config(i2c0_A, i2c1_B, channel)
        try:
            data = bus.readfrom_mem(dev_addr, start_mem_addr, length, addrsize=16)
            return data
        except OSError:
            print(f"[ERROR]: Fallo al leer bloque de EEPROM Canal {channel} ({hex(dev_addr)})")
            return None