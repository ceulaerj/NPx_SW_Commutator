# serdes_vpg.py
import time

# Direcciones de registros del MAX96717 (Banco VTX y Control de Patrón)
REG_PATGEN_CTRL = 0x0240  # PATGEN_0 (Master Enable + VS + HS + DE)
REG_VTX0        = 0x024E  # Control maestro alternativo de sincronismo
REG_PATGEN_SRC  = 0x024F  # Selección de fuente de reloj y OSC PCLK (Bit 7)
REG_PATGEN_MOD  = 0x026B  # Modo del generador (VID_PRBS_EN, GRAD_MODE, PATGEN_MODE)

class SerDesVideoPatternTest:
    def __init__(self, controller_A, controller_B, hw_driver):
        self.ctrl_A = controller_A
        self.ctrl_B = controller_B
        self.hw = hw_driver

    def enable_serializer_vpg(self, channel_id):
        """Configura y enciende el VPG 1080p60 en el SERIALIZADOR (MAX96717) asegurando enrutamiento a Link A"""
        ctrl = self.ctrl_A if channel_id == 'A' else self.ctrl_B
        ser_addr = ctrl.ser_addr
        
        print(f"[VPG]: Configurando Transmisor VPG 1080p60 en Canal {channel_id} (Forzando Link A)...")
        
        # 1. REQUISITO DE HARDWARE: El VPG exige operar en Pixel Mode (Tun_Mode = 0)
        ctrl._write_reg(ser_addr, 0x0383, 0x00) # Asegurar Tun_Mode = 0 (Pixel Mode)
        
        # 2. ASEGURAR ENRUTAMIENTO AL LINK A FÍSICO EN AMBOS SERIALIZADORES
        # Registro 0x0310: Configuración de Stream / Tunneling / Mapeo a Link A (Bits [1:0] = 00 para Link A)
        ctrl._write_reg(ser_addr, 0x0310, 0x01) # Tunneling Mode ON + Mapeo a Link A
        
        # 3. Configuración de Reloj, Sincronismo y Tipo de Dato
        ctrl._write_reg(ser_addr, REG_PATGEN_SRC, 0x8D) # OSC PCLK 150MHz ON (Bit 7 = 1) + Fuente de reloj
        ctrl._write_reg(ser_addr, 0x0243, 0x24)        # Data Type MIPI = RGB888 (0x24)
        ctrl._write_reg(ser_addr, 0x0241, 0x00)        # Virtual Channel (VC) = 0
        
        # Sincronismo interno maestro (VTX0)
        ctrl._write_reg(ser_addr, REG_VTX0, 0xE3)       # GEN_VS, GEN_HS, GEN_DE + VTG_MODE = 11 (Free running)
        
        # 4. Timings Totales 1080p60 (Active + Blanking Interval)
        ctrl._write_reg(ser_addr, 0x0261, 0x08) # H-Total = 2200 (0x0898)
        ctrl._write_reg(ser_addr, 0x0262, 0x98)
        ctrl._write_reg(ser_addr, 0x0263, 0x04) # V-Total = 1125 (0x0465)
        ctrl._write_reg(ser_addr, 0x0264, 0x65)
        
        # 5. Timings Activos (1920x1080)
        ctrl._write_reg(ser_addr, 0x0265, 0x07) # H-Active = 1920 (0x0780)
        ctrl._write_reg(ser_addr, 0x0266, 0x80)
        ctrl._write_reg(ser_addr, 0x0269, 0x04) # V-Active = 1080 (0x0438)
        ctrl._write_reg(ser_addr, 0x026A, 0x38)
        
        # 6. Selección de Patrón y Encendido Maestro
        ctrl._write_reg(ser_addr, REG_PATGEN_MOD, 0x01)  # PATGEN_MODE = 01 (Checkerboard / Ajedrez)
        ctrl._write_reg(ser_addr, REG_PATGEN_CTRL, 0x87) # PATGEN Master Enable (Bit 7 = 1 + VS + HS + DE)
        
        # 7. Aplicar Reseteo One-Shot para aplicar la nueva lógica de tiempos
        ctrl._write_reg(ser_addr, 0x0010, 0x20) # RESET_ONESHOT = 1
        time.sleep_ms(50)
        print(f"[VPG]: Transmisor VPG activo y sincronizado en Canal {channel_id} (Link A).")

    def disable_vpg(self, channel_id):
        ctrl = self.ctrl_A if channel_id == 'A' else self.ctrl_B
        ser_addr = ctrl.ser_addr
        print(f"[VPG]: Desactivando VPG en Transmisor {channel_id}...")
        
        # Desactivar habilitadores y modos de patrón
        ctrl._write_reg(ser_addr, REG_PATGEN_CTRL, 0x00)
        ctrl._write_reg(ser_addr, REG_PATGEN_MOD, 0x00)
        ctrl._write_reg(ser_addr, REG_VTX0, 0x00)
        
        print(f"[VPG]: Transmisor VPG desactivado en Canal {channel_id}.")