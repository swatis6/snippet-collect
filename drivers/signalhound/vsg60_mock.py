from ..instrument_mock import InstrumentMock
from . import vsg60


class VSG60Mock(InstrumentMock):
    def __init__(self, port: int = 5024, timeout: int = 100000,
                 debug: bool = False):
        super().__init__(f'TCPIP0::127.0.0.1::{port}::SOCKET', timeout, debug)
        self.disable_rf()
        self.disable_mod()

        self.rf_enabled = False
        self.mod_enabled = False
        self.freq = 1e9
        self.freq_step = 1e6
        self.power = -20.0
        self.power_step = 10.0
        self.am_enabled = False
        self.am_freq = 1e3
        self.am_shape = 'SINE'
        self.am_depth = 50.0
        self.fm_enabled = False
        self.fm_freq = 1e3
        self.fm_shape = 'SINE'
        self.fm_dev = 1e3
        self.pulse_enabled = False
        self.pulse_trig = 'CONT'
        self.pulse_width = 1e-3
        self.pulse_period = 2e-3

    def disconnect(self):
        self.disable_rf()
        self.disable_mod()
        self._close()

    def show_app(self):
        self._write('DISP:HIDE 0')

    def hide_app(self):
        self._write('DISP:HIDE 1')

    #------------------------------#  OUTPUT  #------------------------------#

    def enable_rf(self):
        self._write('OUTP 1')
        self.rf_enabled = True

    def disable_rf(self):
        self._write('OUTP 0')
        self.rf_enabled = False

    def has_rf_enabled(self) -> bool:
        self._query('OUTP?')
        return self.rf_enabled

    def enable_mod(self):
        self._write('OUTP:MOD 1')
        self.mod_enabled = True

    def disable_mod(self):
        self._write('OUTP:MOD 0')
        self.mod_enabled = False

    def has_mod_enabled(self) -> bool:
        self._query('OUTP:MOD?')
        return self.mod_enabled

    #----------------------------#  FREQUENCY  #----------------------------#

    def set_freq(self, freq_mhz: float):
        """Set the output frequency of the VSG."""
        self._write(f'FREQ {freq_mhz}MHz')
        self.freq = freq_mhz*1e6

    def get_freq(self) -> float:
        """Get the output frequency of the VSG."""
        self._query('FREQ?')
        return self.freq

    def set_freq_step(self, step_mhz: float):
        self._write(f'FREQ:STEP {step_mhz}MHz')
        self.freq_step = step_mhz*1e6

    def get_freq_step(self) -> float:
        self._query(f'FREQ:STEP?')
        return self.freq_step

    #------------------------------#  POWER  #------------------------------#

    def set_power(self, power_dbm: float):
        """sets the output power in dBm"""
        self._write(f'POW {power_dbm}')
        self.power = power_dbm

    def get_power(self) -> float:
        self._query('POW?')
        return self.power

    def set_power_step(self, power_step_db: float):
        self._write(f'POW:STEP {power_step_db}')
        self.power_step = power_step_db

    def get_power_step(self) -> float:
        self._query('POW:STEP?')
        return self.power_step

    #-----------------------#  Amplitude Modulation  #-----------------------#

    def enable_am(self):
        self._write('AM 1')
        self.am_enabled = True

    def disable_am(self):
        self._write('AM 0')
        self.am_enabled = False

    def has_am_enabled(self) -> bool:
        self._query('AM?')
        return self.am_enabled

    def set_am_frequency(self, frequency_khz: float):
        self._write(f'AM:FREQ {frequency_khz}kHz')
        self.am_freq = frequency_khz*1e3

    def get_am_frequency(self) -> float:
        self._query('AM:FREQ?')
        return self.am_freq
    
    def set_am_shape(self, shape: str):
        self._write(f'AM:SHAP {vsg60.MOD_SHAPE[shape]}')
        self.am_shape = shape

    def get_am_shape(self) -> str:
        self._query('AM:SHAP?')
        return self.am_shape

    def set_am_depth(self, depth: int):
        self._write(f'AM:DEPT {depth}')
        self.am_depth = depth

    def get_am_depth(self) -> int:
        self._query('AM:DEPT?')
        return self.am_depth

    def config_am(self, freq_khz: float, shape: str, depth: int):
        self.enable_am()
        self.set_am_frequency(freq_khz)
        self.set_am_shape(shape)
        self.set_am_depth(depth)

    #-----------------------#  Frequency Modulation  #-----------------------#

    def enable_fm(self):
        self._write('FM 1')
        self.fm_enabled = True

    def disable_fm(self):
        self._write('FM 0')
        self.fm_enabled = False

    def has_fm_enabled(self) -> bool:
        self._query('FM?')
        return self.fm_enabled
    
    def set_fm_frequency(self, frequency_khz: float):
        self._write(f'FM:FREQ {frequency_khz}kHz')
        self.fm_freq = frequency_khz*1e3
        
    def get_fm_frequency(self) -> float:
        self._query('FM:FREQ?')
        return self.fm_freq
    
    def set_fm_shape(self, shape: str):
        self._write(f'FM:SHAP {vsg60.MOD_SHAPE[shape]}')
        self.fm_shape = shape

    def get_fm_shape(self) -> str:
        self._query('FM:SHAP?')
        return self.fm_shape
    
    def set_fm_deviation(self, deviation_khz: float):
        self._write(f'FM:DEV {deviation_khz}kHz')
        self.fm_deviation = deviation_khz*1e3

    def get_fm_deviation(self) -> float:
        self._query('FM:DEV?')
        return self.fm_deviation

    def config_fm(self, freq_khz: float, shape: str, 
                  deviation_khz: float):
        self.enable_fm()
        self.set_fm_frequency(freq_khz)
        self.set_fm_shape(shape)
        self.set_fm_deviation(deviation_khz)

    #-----------------------#  Pulse Modulation  #-----------------------#

    def enable_pulse(self):
        self._write('PULM 1')
        self.pulse_enabled = True

    def disable_pulse(self):
        self._write('PULM 0')
        self.pulse_enabled = False

    def has_pulse_enabled(self) -> bool:
        self._query('PULM?')
        return self.pulse_enabled

    def set_pulse_trigger(self, trigger: vsg60.Trigger):
        self._write(f'PULM:TRIG:TYPE {trigger.value}')
        self.pulse_trig = trigger.value

    def get_pulse_trigger(self) -> str:
        self._query('PULM:TRIG:TYPE?')
        return self.pulse_trig
    
    def set_pulse_width(self, width_ms: float):
        self._write(f'PULM:INT:PWID {width_ms}ms')
        self.pulse_width = width_ms*1e-3

    def get_pulse_width(self) -> float:
        self._query('PULM:INT:PWID?')
        return self.pulse_width

    def set_pulse_period(self, period_ms: float):
        self._write(f'PULM:INT:PER {period_ms}ms')
        self.pulse_period = period_ms*1e-3

    def get_pulse_period(self) -> float:
        self._query('PULM:INT:PER?')
        return self.pulse_period
    
    def config_pulse(self, trigger: vsg60.Trigger, width_ms: float,
                     period_ms: float):
        self.enable_pulse()
        self.set_pulse_trigger(trigger)
        self.set_pulse_width(width_ms)
        self.set_pulse_period(period_ms)
