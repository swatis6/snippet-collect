from enum import Enum

from ..instrument import Instrument


MOD_SHAPE = {
    'Sine': 'SINE',
    'Triangle': 'TRI',
    'Square': 'SQU',
    'Ramp': 'RAMP'
}


class Trigger(Enum):
    SINGLE = 'SING'
    CONTINUOUS = 'CONT'


class VSG60(Instrument):
    def __init__(self, port: int = 5024, timeout: int = 100000,
                 debug: bool = False):
        super().__init__(f'TCPIP0::127.0.0.1::{port}::SOCKET', timeout, debug)

        self.inst.read_termination = '\n'
        self.inst.write_termination = '\n'

        (vendor, device, sn, _) = self.get_id().split(',')
        print(f'Connected to {vendor} {device}, SN: {sn}')

        self.disable_rf()

    def disconnect(self):
        self.disable_rf()
        self._close()

    def show_app(self):
        self._write('DISP:HIDE 0')

    def hide_app(self):
        self._write('DISP:HIDE 1')

    #------------------------------#  OUTPUT  #------------------------------#

    def enable_rf(self):
        self._write('OUTP 1')

    def disable_rf(self):
        self._write('OUTP 0')

    def has_rf_enabled(self) -> bool:
        return bool(self._query('OUTP?'))

    def enable_mod(self):
        self._write('OUTP:MOD 1')

    def disable_mod(self):
        self._write('OUTP:MOD 0')

    def has_mod_enabled(self) -> bool:
        return bool(self._query('OUTP:MOD?'))

    #----------------------------#  FREQUENCY  #----------------------------#

    def set_freq(self, freq_hz: float):
        """Set the output frequency of the VSG."""
        self._write(f'FREQ {freq_hz}Hz')

    def get_freq(self) -> float:
        """Get the output frequency of the VSG."""
        return float(self._query('FREQ?'))

    def set_freq_step(self, step_mhz: float):
        self._write(f'FREQ:STEP {step_mhz}MHz')

    def get_freq_step(self) -> float:
        return float(self._query(f'FREQ:STEP?'))

    #------------------------------#  POWER  #------------------------------#

    def set_power(self, power_dbm: float):
        """sets the output power in dBm"""
        self._write(f'POW {power_dbm}')

    def get_power(self) -> float:
        return float(self._query('POW?'))

    def set_power_step(self, power_step_db: float):
        self._write(f'POW:STEP {power_step_db}')

    def get_power_step(self) -> float:
        return float(self._query('POW:STEP?'))

    #-----------------------#  Amplitude Modulation  #-----------------------#

    def enable_am(self):
        self._write('AM 1')

    def disable_am(self):
        self._write('AM 0')

    def has_am_enabled(self) -> str:
        return self._query('AM?')

    def set_am_frequency(self, frequency_khz: float):
        self._write(f'AM:FREQ {frequency_khz}kHz')

    def get_am_frequency(self) -> float:
        return float(self._query('AM:FREQ?'))
    
    def set_am_shape(self, shape: str):
        self._write(f'AM:SHAP {MOD_SHAPE[shape]}')

    def get_am_shape(self) -> str:
        return self._query('AM:SHAP?')

    def set_am_depth(self, depth: int):
        self._write(f'AM:DEPT {depth}')

    def get_am_depth(self) -> int:
        return int(self._query('AM:DEPT?'))

    def config_am(self, freq_khz: float, shape: str, depth: int):
        self.enable_am()
        self.set_am_frequency(freq_khz)
        self.set_am_shape(shape)
        self.set_am_depth(depth)

    #-----------------------#  Frequency Modulation  #-----------------------#

    def enable_fm(self):
        self._write('FM 1')

    def disable_fm(self):
        self._write('FM 0')

    def has_fm_enabled(self) -> str:
        return self._query('FM?')
    
    def set_fm_frequency(self, frequency_khz: float):
        self._write(f'FM:FREQ {frequency_khz}kHz')

    def get_fm_frequency(self) -> float:
        return float(self._query('FM:FREQ?'))
    
    def set_fm_shape(self, shape: str):
        self._write(f'FM:SHAP {MOD_SHAPE[shape]}')

    def get_fm_shape(self) -> str:
        return self._query('FM:SHAP?')
    
    def set_fm_deviation(self, deviation_khz: float):
        self._write(f'FM:DEV {deviation_khz}kHz')

    def get_fm_deviation(self) -> float:
        return float(self._query('FM:DEV?'))

    def config_fm(self, freq_khz: float, shape: str, 
                  deviation_khz: float):
        self.enable_fm()
        self.set_fm_frequency(freq_khz)
        self.set_fm_shape(shape)
        self.set_fm_deviation(deviation_khz)

    #-----------------------#  Pulse Modulation  #-----------------------#

    def enable_pulse(self):
        self._write('PULM 1')

    def disable_pulse(self):
        self._write('PULM 0')

    def has_pulse_enabled(self) -> str:
        return self._query('PULM?')

    def set_pulse_trigger(self, trigger: Trigger):
        self._write(f'PULM:TRIG:TYPE {trigger.value}')

    def get_pulse_trigger(self) -> str:
        return self._query('PULM:TRIG:TYPE?')
    
    def set_pulse_width(self, width_ms: float):
        self._write(f'PULM:INT:PWID {width_ms}ms')

    def get_pulse_width(self) -> float:
        return float(self._query('PULM:INT:PWID?'))

    def set_pulse_period(self, period_ms: float):
        self._write(f'PULM:INT:PER {period_ms}ms')

    def get_pulse_period(self) -> float:
        return float(self._query('PULM:INT:PER?'))

    def config_pulse(self, trigger: Trigger, width_ms: float,
                     period_ms: float):
        self.enable_pulse()
        self.set_pulse_trigger(trigger)
        self.set_pulse_width(width_ms)
        self.set_pulse_period(period_ms)

    #-----------------------#  Multitone Modulation  #-----------------------#

    def enable_multitone(self):
        self._write('MTON 1')

    def disable_multitone(self):
        self._write('MTON 0')

    def has_multitone_enabled(self) -> str:
        return self._query('MTON?')

    def set_multitone_phase(self, phase: str):
        self._write(f'MTON:PHAS {phase}')

    def get_multitone_phase(self) -> str:
        return self._query('MTON:PHAS?')
    
    def set_multitone_seed(self, seed: int):
        self._write(f'MTON:PHAS:SEED {seed}')

    def get_multitone_seed(self) -> int:
        return self._query('MTON:PHAS:SEED?')
    
    def set_multitone_tone_count(self, count: int):
        self._write(f'MTON:NTON {count}')

    def get_multitone_tone_count(self) -> int:
        return self._query('MTON:NTON?')
    
    def set_multitone_freq_spacing_khz(self, spacing_khz: float):
        self._write(f'MTON:FSP {spacing_khz}kHz')

    def get_multitone_freq_spacing(self) -> str:
        return self._query('MTON:FSP?')
    
    def set_multitone_notch_width_khz(self, width_khz: float):
        self._write(f'MTON:FNOT {width_khz}kHz')

    def get_multitone_notch_width(self) -> str:
        return self._query('MTON:FNOT?')

    def config_multitone(self, phase: str, seed: int, count: int,
                         spacing_khz: float, width_khz: float):
        self.enable_multitone()
        self.set_multitone_phase(phase)
        self.set_multitone_seed(seed)
        self.set_multitone_freq_spacing_khz(spacing_khz)
        self.set_multitone_tone_count(int(count))
        self.set_multitone_notch_width_khz(width_khz)

    #-----------------------#  Step Sweep Modulation  #-----------------------#

    def enable_step_sweep(self):
        self._write('STEP 1')

    def disable_step_sweep(self):
        self._write('STEP 0')

    def has_step_sweep_enabled(self) -> str:
        return self._query('STEP?')

    def set_step_sweep_trigger(self, trigger: Trigger):
        self._write(f'STEP:TRIG:TYPE {trigger.value}')

    def get_step_sweep_trigger(self) -> str:
        return self._query('STEP:TRIG:TYPE?')
    
    def set_step_sweep_type(self, type: str):
        self._write(f'STEP:TYPE {type}')

    def get_step_sweep_type(self) -> str:
        return self._query('STEP:TYPE?')
    
    def set_step_sweep_freq_range_khz(self, start_khz: float, stop_khz: float,
                                      points: int):
        self._write(f'STEP:FREQ:STAR {start_khz}kHz')
        self._write(f'STEP:FREQ:STOP {stop_khz}kHz')
        self._write(f'STEP:POIN {points}')

    def get_step_sweep_freq_start(self) -> str:
        return self._query('STEP:FREQ:STAR?')
    
    def get_step_sweep_freq_stop(self) -> str:
        return self._query('STEP:FREQ_STOP?')
    
    def get_step_sweep_points(self) -> int:
        return self._query('STEP:POIN?')

    def set_step_sweep_amplitude_range_dbm(self, start: float, stop: float):
        self._write(f'STEP:AMPL:STAR {start}')
        self._write(f'STEP:AMPL:STOP {stop}')

    def get_step_sweep_amplitude_start(self) -> int:
        return self._query('STEP:AMPL:STAR?')
    
    def get_step_sweep_amplitude_stop(self) -> int:
        return self._query('STEP:AMPL:STOP?')
    
    def set_step_sweep_dwell_ms(self, dwell_ms: float):
        self._write(f'STEP:DWEL {dwell_ms}ms')

    def get_step_sweep_dwell(self) -> str:
        return self._query('STEP:DWEL?')
    
    def config_step_sweep_freq(self, trigger: Trigger,
                               freq_start_khz: float, freq_stop_khz: float,
                               points: int, dwell_ms: float):
        self.enable_step_sweep()
        self.set_step_sweep_trigger(trigger)
        self.set_step_sweep_type('FREQ')
        self.set_step_sweep_freq_range_khz(freq_start_khz, freq_stop_khz, points)
        self.set_step_sweep_dwell_ms(dwell_ms)

    def config_step_sweep_freq_and_ampl(
            self, trigger: Trigger,
            freq_start_khz: float, freq_stop_khz: float, points: int,
            ampl_start_dbm: float, ampl_stop_dbm: float, dwell_ms: float):
        self.enable_step_sweep()
        self.set_step_sweep_trigger(trigger)
        self.set_step_sweep_type('FREQAMPL')
        self.set_step_sweep_freq_range_khz(freq_start_khz, freq_stop_khz, points)
        self.set_step_sweep_amplitude_range_dbm(ampl_start_dbm, ampl_stop_dbm)
        self.set_step_sweep_dwell_ms(dwell_ms)

    #-----------------------#  Ramp Sweep Modulation  #-----------------------#

    def enable_ramp_sweep(self):
        self._write('RAMP 1')

    def disable_ramp_sweep(self):
        self._write('RAMP 0')

    def has_ramp_sweep_enabled(self) -> str:
        return self._query('RAMP?')

    def set_ramp_sweep_trigger(self, trigger: Trigger):
        self._write(f'RAMP:TRIG:TYPE {trigger.value}')

    def get_ramp_sweep_trigger(self) -> str:
        return self._query('RAMP:TRIG:TYPE?')
    
    def set_ramp_sweep_span_khz(self, span_khz: float):
        self._write(f'RAMP:FREQ:SPAN {span_khz}kHz')

    def get_ramp_sweep_span(self) -> str:
        return self._query('RAMP:FREQ:SPAN?')
    
    def set_ramp_sweep_time_ms(self, time_ms: float):
        self._write(f'RAMP:SWE:TIME {time_ms}ms')

    def get_ramp_sweep_time(self) -> str:
        return self._query('RAMP:SWE:TIME?')
    
    def set_ramp_sweep_period_ms(self, period_ms: float):
        self._write(f'RAMP:SWE:PER {period_ms}ms')

    def get_ramp_sweep_period(self) -> str:
        return self._query('RAMP:SWE:PER?')
    
    def config_ramp_sweep(self, trigger: Trigger, span_khz: float,
                          time_ms: float, period_ms: float):
        self.enable_ramp_sweep()
        self.set_ramp_sweep_trigger(trigger)
        self.set_ramp_sweep_span_khz(span_khz)
        self.set_ramp_sweep_time_ms(time_ms)
        self.set_ramp_sweep_period_ms(period_ms)

    #-----------------------#  AWGN Modulation  #-----------------------#

    def enable_awgn(self):
        self._write('RAD:AWGN 1')

    def disable_awgn(self):
        self._write('RAD:AWGN 0')

    def has_awgn_enabled(self) -> str:
        return self._query('RAD:AWGN?')
    
    def set_awgn_bandwidth_khz(self, bw_khz: float):
        self._write(f'RAD:AWGN:BWID {bw_khz}kHz')

    def get_awgn_bandwidth(self) -> str:
        return self._query('RAD:AWGN:BWID?')
    
    def set_awgn_length_ms(self, length_ms: float):
        self._write(f'RAD:AWGN:LEN {length_ms}ms')

    def get_awgn_length(self) -> str:
        return self._query('RAD:AWGN:LEN?')
    
    def set_awgn_seed(self, seed: int):
        self._write(f'RAD:AWGN:SEED {seed}')

    def get_awgn_seed(self) -> str:
        return self._query('RAD:AWGN:SEED?')

    def config_awgn(self, bw_khz: float, length_ms: float, seed: int):
        self.enable_awgn()
        self.set_awgn_bandwidth_khz(bw_khz)
        self.set_awgn_length_ms(length_ms)
        self.set_awgn_seed(seed)
