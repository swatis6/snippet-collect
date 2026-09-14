from ..instrument import Instrument


class Spike(Instrument):
    def __init__(self, port: int = 5025, timeout: int = 100000,
                 debug: bool = False):
        super().__init__(f'TCPIP0::127.0.0.1::{port}::SOCKET', timeout, debug)

        self.inst.read_termination = '\n'
        self.inst.write_termination = '\n'

        (vendor, device, sn, _) = self.get_id().split(',')
        print(f'Connected to {vendor} {device}, SN: {sn}')

    def disconnect(self):
        self._close()

    def show_app(self):
        self._write('DISP:HIDE 0')

    def hide_app(self):
        self._write('DISP:HIDE 1')

    def switch_mode(self, mode: str):
        self._write(f'INST {mode}')

    def set_center_freq(self, freq_hz):
        """Set the center frequency of the spectrum analyzer."""
        self._write(f'FREQ:CENT {freq_hz}Hz')

    def get_center_freq(self):
        """Get the center frequency of the spectrum analyzer."""
        return float(self._query('FREQ:CENT?'))

    def set_start_freq(self, freq_hz):
        """set the start frequency given in Hz"""
        self._write(f'SENS:FREQ:START {freq_hz}Hz')

    def set_stop_freq(self, freq_hz):
        """set the stop frequency given in Hz"""
        self._write(f'SENS:FREQ:STOP {freq_hz}Hz')

    def set_span(self, span_hz):
        """Set the frequency span of the spectrum analyzer."""
        self._write(f'FREQ:SPAN {span_hz}Hz')

    def get_span(self):
        """Get the frequency span of the spectrum analyzer."""
        return float(self._query('FREQ:SPAN?'))

    def set_reference_level(self, level: float):
        """Set the reference level of the spectrum analyzer."""
        self._write(f'POW:RLEV {level}DBM')

    def get_reference_level(self):
        """Get the reference level of the spectrum analyzer."""
        return float(self._query('POW:RLEV?'))
    
    def set_div(self, div):
        #Sets division value
        self._write(f'POW:PDIV {div}')

    def get_div(self):
        #Retrieves division value
        return self._query('POW:PDIV?')

    def set_atten(self, dBm):
        #Sets the attenuation on the spec an
        self._write(f'POW:ATT {dBm}')
    
    def get_atten(self):
        #Retrieves the attenuation value 
        return self._write('POW:ATT?')

    def set_gain(self, gain):
        self._write(f'POW:GAIN {gain}')

    def get_gain(self):
        #Retrieves the gain value
        return self._write('POW:GAIN?')
    
    def set_preamp(self, preamp):
        self._write(f'POW:PREAMP {preamp}')

    def get_preamp(self):
        #Retrieves preamp level
        return self._query('POW:PREAMP?')
    
    def enable_marker(self, id: int):
        self._write(f'CALC:MARK:SEL {id}')
        self._write('CALC:MARK:STAT ON')
        # Set marker on current trace
        self._write('CALC:MARK:MODE POS')
        self._write('CALC:MARK:UPD ON')
        self._write(f'CALC:MARK:PKTR ON')
    
    def set_marker(self, id: int, freq: float):
        self._write(f'CALC:MARK:SEL {id}')
        self._write(f'CALC:MARK:X {freq}')
    
    def get_marker(self, id: int | None = None):
        if id is not None:
            self._write(f'CALC:MARK:SEL {id}')
        return self._query('CALC:MARK:Y?')

    def activate_marker(self, marker_number, mode, frequency = None,
                        peak_tracking = False):
        """Activate a position marker at a specified frequency or enable
           peak tracking.
        """
        self._write(f'CALC:MARK:SEL {marker_number}')
        self._write('CALC:MARK:STAT ON')
        self._write(f'CALC:MARK:MODE {mode}')
        self._write('CALC:MARK:UPD ON')
        if peak_tracking:
            self._write('CALC:MARK:PKTR ON')
        else:
            self._write('CALC:MARK:PKTR OFF')
            self._write(f'CALC:MARK:X {frequency}Hz')
    
    def marker_mode(self, marker_number = 1, mode = 'POS'):
        """Change the marker mode"""
        if mode in ['POSition', 'POS', 'NOISE','CHPower','CHP','NDB']:
            command = f'CALC:MARK:SEL {marker_number}'
            self._write(command)
            # move the marker to the position
            command = f'CALC:MARK:MODE {mode}'
            self._write(command)
        else:
            print('Wrong mode')
    
    def marker_position(self, marker_number=1, frequency=1e9):
        """Move the specified marker position"""
        command = f'CALC:MARK:SEL {marker_number}'
        self._write(command)
        # TODO: check that the marker does not have peak tracking

        # move the marker to the position
        command = f'CALC:MARK:X {frequency}Hz'
        self._write(command)

    def get_marker_values(self, mark_num):
        """Get the amplitude and frequency values of a specified marker."""
        self._write(f'CALC:MARK:SEL {mark_num}')
        frequency = self._query('CALC:MARK:X?')
        amplitude = self._query('CALC:MARK:Y?')
        return float(frequency), float(amplitude)
    
    def set_avg_trace(self, count):
        """sets the trace to an average trace based on the passed in count"""
        cmd = "TRAC:TYPE AVER"
        self._write(cmd)
        cmd = f"TRAC:AVER:COUN {count}"
        self._write(cmd)

    def get_avg_count(self):
        """ gets and returns the average count""" 
        cmd = "TRAC:AVER:COUN?"
        return int(self._query(cmd))

    def get_curr_avg(self):
        """gets and returns the current number of averages"""
        cmd = "TRAC:AVER:CURR?"
        return int(self._query(cmd))

    def clear_trace(self, trace_num: int = 1):
        """clears the specified trace"""
        self._write(f'TRAC:SEL {trace_num}')
        self._write(f"TRAC:CLE")

    def clear_all_traces(self):
        """clears all traces"""
        cmd = "TRAC:CLE:ALL"
        self._write(cmd)
    
    def set_max_hold_trace(self, trace_num: int = 1):
        self._write(f'TRAC:SEL {trace_num}')
        self._write('TRAC:TYPE MAXH')
        
        
    def channel_power_state(self, state):
        """turns on/off the use of the channel power"""
        cmd = f'SENS:CHP:STAT {state}'
        self._write(cmd)

    def set_channel_power_trace(self, trace):
        """sets the channel power trace"""
        cmd = f'SENS:CHP:TRAC {trace}'
        self._write(cmd)

    def set_channel_power_width(self, width_hz: float):
        """sets the channel power width"""
        cmd = f'SENS:CHP:WID {width_hz}Hz'
        self._write(cmd)

    def set_adj_channel_state(self, channel: int, state):
        """Sets the state for a given adjacent channel to either ON or OFF"""
        self._write(f'CHP:CHAN:STAT {channel},{state}')

    def set_adj_channel_width(self, channel: int, width):
        """Sets the width for a given adjacent channel"""
        self._write(f'CHP:CHAN:WID {channel},{width}')

    def set_adj_channel_offset(self, channel: int, offset):
        """Sets the offset for a given adjacent channel"""
        self._write(f'CHP:CHAN:OFFS {channel},{offset}')

    def configure_adj_channel(self, channel: int, width, offset):
        """Enables and configures a given adjacent channel"""
        self.set_adj_channel_state(channel, 'ON')
        self.set_adj_channel_width(channel, width)
        self.set_adj_channel_offset(channel, offset)

    def get_channel_power(self):
        """Returns the main channel power in dBm"""
        return float(self._query('CHP:CHP?'))

    def get_lower_channel_power(self, channel_num: int = 1):
        """Returns the channel power for a given
           lower adjacent channel in dBm
        """
        return float(self._query(f'CHP:CHP:LOW? {channel_num}'))

    def get_upper_channel_power(self, channel_num: int = 1):
        """Returns the channel power for a given
           upper adjacent channel in dBm
        """
        return float(self._query(f'CHP:CHP:UPP? {channel_num}'))

    def set_RBW(self, freq_hz):
        """sets the rbw value to the passed in frequncy"""
        self._write(f'BAND {freq_hz}Hz')

    def get_RBW(self):
        """gets the rbw value"""
        return int(self._query('BAND?'))
    
    def set_center_IQ(self, freq_hz):
        """sets the center frequency (Hz) for IQ capture"""
        self.switch_mode('ZS') # Enter zero-span mode
        self._write(f'ZS:CAP:CENT {freq_hz}Hz')

    def get_ref_lvl_IQ(self):
        return float(self._query('ZS:CAP:RLEV?'))
    
    def set_ref_lvl_IQ(self, ref_lvl: float):
        self._write(f'ZS:CAP:RLEV {ref_lvl}DBM')

    def get_center_IQ(self):
        cmd = f'ZS:CAP:CENT?'
        return float(self._query(cmd))
    
    def set_srate_IQ(self, srate_hz):
        cmd = f'ZS:CAP:SRAT {srate_hz}Hz'
        self._write(cmd)
    
    def get_srate_IQ(self):
        cmd = f'ZS:CAP:SRAT?'
        return float(self._query(cmd))
    
    def set_IFBW_IQ(self, bw_hz):
        cmd = f'ZS:CAP:IFBW {bw_hz}Hz'
        self._write(cmd)

    def get_IFBW_IQ(self):
        cmd = f'ZS:CAP:IFBW?'
        return float(self._query(cmd))
    
    def set_sweep_time_IQ(self, sweep_ms: float):
        cmd = f'ZS:CAP:SWE:TIME {sweep_ms/1e3}'
        self._write(cmd)

    def get_sweep_time_IQ(self):
        return float(self._query(f'ZS:CAP:SWE:TIME?'))
    
    def get_IQ(self):
        self._write('INIT:CONT ON') # Begin continuous capture, if not already active
        self.switch_mode('ZS') # Enter zero-span mode
        self._write('FORM:IQ ASC') # Send back ascii IQ data
        data = self._query('FETCH:ZS? 1').split(',')
        complex_data = []

        # ASCII CONVERSION, VERY SLOW TRANSFER
        real = float('-inf') # Placeholder value
        for i in range(len(data)):
            if not i%2: # Real value
                real = data[i]
            else: # Imaginary value
                complex_data.append(float(real) + float(data[i])*1j)
        
        return complex_data
    
    def get_pwr(self) -> list[float]:
        return [float(val) for val in self._query('TRAC?').split(',')]
    
    def get_max_dbm(self) -> float:
        """Retrieves the last peak power level in dBm"""
        return float(self._query('FETC:BLE 4'))
