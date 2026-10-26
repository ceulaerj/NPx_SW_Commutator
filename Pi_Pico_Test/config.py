class PicoConfig:
    """Configuration class for Raspberry Pi Pico pin settings and timing"""
    
    # Timing configuration
    TOGGLE_PERIOD_MS = 100  # Time between pin toggles in milliseconds
    
    # Pin configuration
    class Pins:
        INPUT = 19
        OUTPUT = 20
        LED = 25
    
    # Pin modes
    class PinModes:
        INPUT_MODE = "IN"
        OUTPUT_MODE = "OUT"
        PULL_DOWN = "PULL_DOWN"
    
    # Timer configuration
    class Timer:
        PERIODIC = "PERIODIC"
        ONE_SHOT = "ONE_SHOT" 