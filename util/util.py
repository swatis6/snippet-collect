from datetime import datetime as dt
import math


KHZ = 1e3
MHZ = 1e6
GHZ = 1e9

FREQ_UNITS = {
    'Hz': 1,
    'kHz': KHZ,
    'MHz': MHZ,
    'GHz': GHZ
}


def dbm_to_vpp(power: float) -> float:
    """Convert power in dBm to Vpp at 50 ohms."""
    return math.sqrt(0.4) * 10**(power / 20)

def wait_until(target_time: dt):
    """Wait until the specified target_time."""
    current_time = dt.now()
    while current_time < target_time:
        current_time = dt.now()
