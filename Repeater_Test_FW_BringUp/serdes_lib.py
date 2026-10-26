# serdes_lib.py
# Native control library for MAX96716A and MAX96717 (Tunneling + RoR Mode)
# Target: NPNXT_RPTST_00 on Raspberry Pi Pico (RP2040)
# Canal A: bus I2C0 hardware (GP0=SDA, GP1=SCL) — instanciado en main.py
# Canal B: bus I2C1 hardware (GP2=SDA, GP3=SCL) — instanciado en main.py

from machine import I2C
import time

class SerDesController:
    def __init__(self, i2c_bus: I2C, des_addr=0x6A, ser_addr=0x40): # 8-bits addresses des_addr=0xD4, ser_addr=0x80
        """
        Initializes the controller for a specific SerDes channel.
        des_addr: 7-bit I2C address of the MAX96716A Deserializer (0x6A equals 0xD4 in 8-bit) [cite: 14, 59, 1933]
        ser_addr: 7-bit I2C address of the MAX96717 Serializer (Default or alias address) [cite: 97, 126]
        """
        self.i2c = i2c_bus
        self.des_addr = des_addr
        self.ser_addr = ser_addr

    def _write_reg(self, dev_addr, reg, val):
        """Writes one byte to a 16-bit register address (Standard Maxim/ADI protocol)."""
        buf = bytearray([(reg >> 8) & 0xFF, reg & 0xFF, val & 0xFF])
        try:
            self.i2c.writeto(dev_addr, buf)
            return True
        except OSError:
            # In RoR mode, the Serializer might return NACK until the back-channel is fully locked
            return False

    def _read_reg(self, dev_addr, reg):
        """Reads one byte from a 16-bit register address."""
        reg_buf = bytearray([(reg >> 8) & 0xFF, reg & 0xFF])
        try:
            self.i2c.writeto(dev_addr, reg_buf)
            time.sleep_ms(2)
            res = self.i2c.readfrom(dev_addr, 1)
            return res[0]
        except OSError:
            return None
        
    def init_deserializer_gmsl2(self):
        print("[GMSL2 DES] Initializing MAX96716A on 7-bit address: 0x{:02X}...".format(self.des_addr))
        
        # 1. Soft Reset AL INICIO para partir de estado limpio
        self._write_reg(self.des_addr, 0x0010, 0x20)
        time.sleep_ms(20)
        
        # ==============================================================================
        # 🛡️ MANDATORY REGISTER PROGRAMMING (Datasheet MAX96716A - Page 65 & 69)
        # ==============================================================================
        val_302 = self._read_reg(self.des_addr, 0x0302)
        if val_302 is not None:
            new_302 = (val_302 & 0x8F) | 0x10
            self._write_reg(self.des_addr, 0x0302, new_302)

        val_10 = self._read_reg(self.des_addr, 0x0010)
        if val_10 is not None:
            self._write_reg(self.des_addr, 0x0010, val_10 | 0x04)

        val_12 = self._read_reg(self.des_addr, 0x0012)
        if val_12 is not None:
            self._write_reg(self.des_addr, 0x0012, val_12 | 0x10)
        
        time.sleep_ms(20)
        # ==============================================================================

        # 2. Habilitar Back-Channel RoR
        self._write_reg(self.des_addr, 0x003F, 0x04)
        
        # 3. Optimización de sensibilidad RX y driver de pin LOCK
        self._write_reg(self.des_addr, 0x1417, 0x0E) # Boost de sensibilidad a 1.5 GHz
        self._write_reg(self.des_addr, 0x0018, 0x20) # Habilitar LED Azul LOCK

        # ==============================================================================
        # 🎥 CONFIGURACIÓN DE VIDEO SYNC PARA VPG / PIXEL MODE
        # ==============================================================================
        # CORREGIDO: Pixel Mode nativo (0x00) en lugar de Tunneling (0x0B) para coherencia con VPG
        self._write_reg(self.des_addr, 0x0474, 0x00) # Pixel Mode ON
        
        # Configurar el comportamiento de pérdida de video (Auto-sync)
        self._write_reg(self.des_addr, 0x03E0, 0x0F) # FSYNC_0: Permitir sincronismo automático
        # ==============================================================================

        # ==============================================================================
        # 🚀 SECUENCIA DE ARRANQUE OBLIGATORIA PARA ACTIVAR EL ENLACE GMSL2
        # ==============================================================================
        self._write_reg(self.des_addr, 0x0010, 0x11) # AUTO_LINK = 1, LINK_CFG = 01 (Link A)
        time.sleep_ms(20)

        val_ctrl0 = self._read_reg(self.des_addr, 0x0010)
        if val_ctrl0 is not None:
            self._write_reg(self.des_addr, 0x0010, val_ctrl0 & ~0x40)

        time.sleep_ms(50)
        print("[GMSL2 LINK]: Secuencia de arranque enviada. El PHY debería intentar el Link Lock.")

    def init_serializer_csi2(self):
        print("[GMSL2 SER] Initializing MAX96717 on 7-bit address: 0x{:02X}...".format(self.ser_addr))
        
        # 1. Soft Reset AL INICIO
        self._write_reg(self.ser_addr, 0x0010, 0x20)
        time.sleep_ms(20)
        
        # 2. Configuración de receptor MIPI CSI-2 a 4 Lanes (0x0308 = 0x04)
        self._write_reg(self.ser_addr, 0x0308, 0x04) # 4-Lanes RX Mode
        self._write_reg(self.ser_addr, 0x0302, 0x40) # Auto-start y calibración D-PHY
        self._write_reg(self.ser_addr, 0x0310, 0x01) # Tunneling Mode / Mapeo Link A
        self._write_reg(self.ser_addr, 0x0313, 0x0F) # Enable 4 Lanes
        
        # 3. Optimización de señal
        self._write_reg(self.ser_addr, 0x14C8, 0x7F) # Amplitud máxima
        self._write_reg(self.ser_addr, 0x14CE, 0x03) # Pre-énfasis alto (validado)

    def set_link_rates(self, dev_addr, tx_rate_val, rx_rate_val):
        """
        Configura las tasas de bits del enlace GMSL2 (TX_RATE y RX_RATE en Reg 0x0001)
        aplicando estrictamente el protocolo de reseteo de la capa física (PHY).
        """
        current_reg1 = self._read_reg(dev_addr, 0x0001)
        if current_reg1 is None:
            print(f"[ERROR]: No se pudo leer el registro 0x0001 en la dirección {hex(dev_addr)}")
            return False
            
        new_reg1 = (current_reg1 & 0xF0) | ((tx_rate_val & 0x03) << 2) | (rx_rate_val & 0x03)
        
        print(f"[GMSL2 LINK]: Actualizando tasas en 0x{dev_addr:02X} a Reg 0x01 = 0x{new_reg1:02X}")
        self._write_reg(dev_addr, 0x0001, new_reg1)
        
        self._write_reg(dev_addr, 0x0010, 0x20)
        time.sleep_ms(50)
        
        print(f"[GMSL2 LINK]: Enlace reiniciado. Esperando re-lock del PLL...")
        return True

    def check_link_lock(self):
        """Monitorea el Lock del PLL en el Deserializador (Bit 3 de 0x0013 según Datasheet)."""
        status = self._read_reg(self.des_addr, 0x0013)
        if status is not None:
            return bool(status & 0x08) # Bit 3 (0x08) = LOCKED (Verificado con Datasheet)
        return False
    
    def get_detailed_lock(self):
        """
        VERDAD ABSOLUTA DE HARDWARE PARA MAX96716A (Basado en Datasheet oficial):
        Bit 3 (0x08) = LOCKED (GMSL link locked)
        Bit 1 (0x02) = CMU_LOCKED / BCC Lock
        """
        status = self._read_reg(self.des_addr, 0x0013)
        if status is not None:
            link_lock = bool(status & 0x08) # Bit 3 = LOCKED
            bcc_lock  = bool(status & 0x02) # Bit 1 = BCC / CMU
            return link_lock, bcc_lock
        return False, False