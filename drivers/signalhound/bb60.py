### Signal Hound BB60 (BB60C/BB60D) native IQ recorder via bb_api (ctypes)
# Records IQ in Spike's exact recorder format: interleaved int16 .iq + .xml sidecar.
# Constants/signatures taken from bb_api.h. Not a pyvisa Instrument - the BB60 IQ
# recorder is not reachable over Spike SCPI, so this talks to the device directly.
#
# Requires the Signal Hound bb_api shared library (bb_api.dll / libbb_api.so) on the
# library path (or pass lib_path). The device must NOT be open in Spike at the same time.

import os
import time
from datetime import datetime as dt
from ctypes import (CDLL, POINTER, byref, c_int, c_uint, c_double, c_float, c_char_p)

import numpy as np

# Default: bb_api.dll sitting in a lib/ folder next to this file (drivers/signalhound/lib/bb_api.dll).
# Resolved from __file__ (not CWD) and only actually loaded when a BB60 is constructed - so the
# module still imports (e.g. for mock runs) even if the DLL isn't present.
_DEFAULT_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib', 'bb_api.dll')

# bb_api.h constants
BB_TRUE = 1
BB_FALSE = 0
BB_AUTO_ATTEN = -1
BB_AUTO_GAIN = -1
BB_STREAMING = 4
BB_STREAM_IQ = 0x0
BB_DATATYPE_32FC = 0 # bbDataType32fc (interleaved 32-bit complex float)
BB_DEVICE_TYPE = {0: 'None', 1: 'BB60A', 2: 'BB60C', 3: 'BB60D'}
BB_MAX_FREQ_HZ = 6.0e9 # BB60C/BB60D upper frequency


class BB60:
    def __init__(self, serial: int = 0, ref_level: float = -20.0,
                 decimation: int = 1, bandwidth_hz: float = 27.0e6,
                 lib_path: str | None = None):
        self._lib = self._load_lib(lib_path)
        self._bind()
        self._decim = int(decimation)
        self._bw = float(bandwidth_hz)
        self.ref_level = float(ref_level)
        # Spike's ScaleFactor: 10^(-refLevel/20). Recover amplitude via (int16/32767)/ScaleFactor
        self.scale_factor = 10 ** (-self.ref_level / 20.0)

        self.handle = c_int(-1)
        if int(serial) == 0:
            self._check(self._lib.bbOpenDevice(byref(self.handle)), 'open first BB60')
        else:
            self._check(self._lib.bbOpenDeviceBySerialNumber(byref(self.handle), int(serial)),
                        f'open BB60 serial {serial}')

        dtype = c_int(0)
        self._lib.bbGetDeviceType(self.handle, byref(dtype))
        self.device_type = BB_DEVICE_TYPE.get(dtype.value, str(dtype.value))
        serial_out = c_uint(0)
        try:
            self._lib.bbGetSerialNumber(self.handle, byref(serial_out))
        except Exception:
            pass
        self.serial = serial_out.value or (int(serial) if serial else 0)
        print(f'Connected to Signal Hound {self.device_type}, SN: {self.serial}')

        self._check(self._lib.bbConfigureRefLevel(self.handle, c_double(self.ref_level)), 'ref level')
        self._check(self._lib.bbConfigureGainAtten(self.handle, BB_AUTO_GAIN, BB_AUTO_ATTEN), 'gain/atten')
        self._check(self._lib.bbConfigureIQDataType(self.handle, BB_DATATYPE_32FC), 'iq data type')

    def _load_lib(self, lib_path):
        candidates = ([lib_path] if lib_path else []) + \
                     [_DEFAULT_LIB, 'bb_api', 'bb_api.dll', 'libbb_api.so', 'libbb_api.dylib']
        last = None
        for c in candidates:
            try:
                return CDLL(c)
            except OSError as e:
                last = e
        raise OSError(f'Could not load bb_api library (set bb-api-lib). Last error: {last}')

    def _bind(self):
        lib = self._lib
        sigs = {
            'bbOpenDevice': [POINTER(c_int)],
            'bbOpenDeviceBySerialNumber': [POINTER(c_int), c_int],
            'bbCloseDevice': [c_int],
            'bbGetDeviceType': [c_int, POINTER(c_int)],
            'bbGetSerialNumber': [c_int, POINTER(c_uint)],
            'bbConfigureRefLevel': [c_int, c_double],
            'bbConfigureGainAtten': [c_int, c_int, c_int],
            'bbConfigureIQCenter': [c_int, c_double],
            'bbConfigureIQ': [c_int, c_int, c_double],
            'bbConfigureIQDataType': [c_int, c_int],
            'bbInitiate': [c_int, c_uint, c_uint],
            'bbQueryIQParameters': [c_int, POINTER(c_double), POINTER(c_double)],
            'bbGetIQUnpacked': [c_int, POINTER(c_float), c_int, POINTER(c_int), c_int, c_int,
                                POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_int)],
            'bbAbort': [c_int],
        }
        for name, argtypes in sigs.items():
            fn = getattr(lib, name)
            fn.argtypes = argtypes
            fn.restype = c_int
        lib.bbGetErrorString.argtypes = [c_int]
        lib.bbGetErrorString.restype = c_char_p

    def _check(self, status, what):
        if status < 0:
            msg = self._lib.bbGetErrorString(status)
            msg = msg.decode() if isinstance(msg, (bytes, bytearray)) else str(msg)
            raise RuntimeError(f'bb_api error during {what}: {msg} ({status})')
        return status

    def _preview(self, flt, n_pts=1025):
        # approximate Spike PreviewTrace: rough spectrum (dBm) of the first samples (thumbnail only)
        z = flt[0::2].astype(np.float64) + 1j * flt[1::2].astype(np.float64)
        N = 2048
        seg = z[:N]
        if seg.size < N:
            seg = np.pad(seg, (0, N - seg.size))
        win = np.hanning(N)
        X = np.fft.fftshift(np.fft.fft(seg * win)) / win.sum()
        dbm = 10.0 * np.log10(np.abs(X) ** 2 + 1e-30)
        return np.interp(np.linspace(0, N - 1, n_pts), np.arange(N), dbm)

    def _write_xml(self, base, center_hz, sample_rate, count, epoch_ns, preview):
        iqname = os.path.abspath(base + '.iq').replace('\\', '/')
        if preview is not None:
            pv = ', '.join(f'{v}' for v in preview) + ', '
            preview_tag = f'    <PreviewTrace>{pv}</PreviewTrace>\n'
        else:
            preview_tag = ''
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<SignalHoundIQFile Version="1.0">\n'
            f'    <DeviceType>{self.device_type}</DeviceType>\n'
            f'    <SerialNumber>{self.serial}</SerialNumber>\n'
            '    <DataType>Complex Short</DataType>\n'
            f'    <ReferenceLevel>{self.ref_level:g}</ReferenceLevel>\n'
            f'    <CenterFrequency>{float(center_hz):.3f}</CenterFrequency>\n'
            f'    <SampleRate>{sample_rate:g}</SampleRate>\n'
            f'    <Decimation>{self._decim}</Decimation>\n'
            f'    <IFBandwidth>{self._bw:g}</IFBandwidth>\n'
            f'    <ScaleFactor>{self.scale_factor:g}</ScaleFactor>\n'
            f'    <IQFileName>{iqname}</IQFileName>\n'
            f'    <EpochNanos>{epoch_ns}</EpochNanos>\n'
            f'{preview_tag}'
            f'    <SampleCount>{count}</SampleCount>\n'
            '</SignalHoundIQFile>\n'
        )
        with open(base + '.xml', 'w') as f:
            f.write(xml)

    def record(self, center_hz, seconds, base, events=None, write_preview=True, stop_event=None):
        """Stream `seconds` of IQ at center_hz to base.iq (Spike int16) + base.xml sidecar.

        events: list of (time_seconds, callable) fired once when the capture crosses that
        time (used to step the VSG RF/power mid-stream). Returns (sample_count, sample_rate).
        Chunks are written as acquired, so RAM stays ~8 MB regardless of capture length.
        """
        lib = self._lib
        self._check(lib.bbConfigureIQCenter(self.handle, c_double(center_hz)), 'iq center')
        self._check(lib.bbConfigureIQ(self.handle, self._decim, c_double(self._bw)), 'configure iq')
        self._check(lib.bbInitiate(self.handle, BB_STREAMING, BB_STREAM_IQ), 'initiate streaming')

        srate, bw = c_double(0), c_double(0)
        self._check(lib.bbQueryIQParameters(self.handle, byref(srate), byref(bw)), 'query iq params')
        sample_rate = srate.value

        # seconds=None -> record until stop_event is set (Tx-controlled collection window)
        total = int(round(sample_rate * seconds)) if seconds else None
        if total is None and stop_event is None:
            raise ValueError('record needs a duration (seconds) or a stop_event')
        chunk = 1 << 20 # ~1M pairs/read (~26 ms @ 40 MS/s)
        buf = np.empty(chunk * 2, dtype=np.float32) # reused 8 MB buffer
        triggers = (c_int * 16)()
        remaining, loss, sec, nano = c_int(0), c_int(0), c_int(0), c_int(0)
        thresholds = sorted(((int(t * sample_rate), fn) for (t, fn) in (events or [])), key=lambda x: x[0])
        preview = None
        epoch_ns = time.time_ns()
        got, ei, first = 0, 0, True
        with open(base + '.iq', 'wb') as f:
            while total is None or got < total:
                if stop_event is not None and stop_event.is_set():
                    break
                n = chunk if total is None else min(chunk, total - got)
                ptr = buf.ctypes.data_as(POINTER(c_float))
                self._check(lib.bbGetIQUnpacked(self.handle, ptr, n, triggers, 16,
                                                BB_TRUE if first else BB_FALSE,
                                                byref(remaining), byref(loss), byref(sec), byref(nano)),
                            'get iq')
                if loss.value:
                    print(f'  WARNING: sample loss at {center_hz / 1e6:g} MHz')
                # Spike format: interleaved int16, scaled to +/-32767 by ScaleFactor
                i16 = np.clip(np.round(buf[:n * 2] * (self.scale_factor * 32767.0)),
                              -32768, 32767).astype('<i2')
                i16.tofile(f)
                if write_preview and preview is None:
                    preview = self._preview(buf[:n * 2].copy())
                got += n
                first = False
                while ei < len(thresholds) and got >= thresholds[ei][0]:
                    thresholds[ei][1]() # fire RF/power step at its sample threshold
                    ei += 1
        lib.bbAbort(self.handle)
        self._write_xml(base, center_hz, sample_rate, got, epoch_ns, preview)
        return got, sample_rate

    def snapshot(self, center_hz, seconds):
        """Capture a short IQ snippet. Returns (complex64 iq, sample_rate_hz, power_dbm)."""
        lib = self._lib
        self._check(lib.bbConfigureIQCenter(self.handle, c_double(center_hz)), 'iq center')
        self._check(lib.bbConfigureIQ(self.handle, self._decim, c_double(self._bw)), 'configure iq')
        self._check(lib.bbInitiate(self.handle, BB_STREAMING, BB_STREAM_IQ), 'initiate streaming')
        srate, bw = c_double(0), c_double(0)
        self._check(lib.bbQueryIQParameters(self.handle, byref(srate), byref(bw)), 'query iq params')
        sample_rate = srate.value

        total = max(1, int(round(sample_rate * seconds)))
        out = np.empty(total * 2, dtype=np.float32)
        triggers = (c_int * 16)()
        remaining, loss, sec, nano = c_int(0), c_int(0), c_int(0), c_int(0)
        got, first, chunk = 0, True, 1 << 18
        while got < total:
            n = min(chunk, total - got)
            ptr = out[got * 2:(got + n) * 2].ctypes.data_as(POINTER(c_float))
            self._check(lib.bbGetIQUnpacked(self.handle, ptr, n, triggers, 16,
                                            BB_TRUE if first else BB_FALSE,
                                            byref(remaining), byref(loss), byref(sec), byref(nano)),
                        'get iq')
            got += n
            first = False
        lib.bbAbort(self.handle)

        iq = out.view(np.complex64)
        p_mw = float(np.mean(iq.real.astype(np.float64) ** 2 + iq.imag.astype(np.float64) ** 2))
        power_dbm = 10.0 * np.log10(p_mw + 1e-30)
        return iq, sample_rate, power_dbm

    def save_snippet(self, base, iq, center_hz, sample_rate, write_preview=False):
        """Write one snippet in Spike int16 .iq + .xml format. Returns the .iq path."""
        flt = np.asarray(iq, dtype=np.complex64).view(np.float32)
        i16 = np.clip(np.round(flt * (self.scale_factor * 32767.0)), -32768, 32767).astype('<i2')
        with open(base + '.iq', 'wb') as f:
            i16.tofile(f)
        preview = self._preview(flt.copy()) if write_preview else None
        self._write_xml(base, center_hz, sample_rate, len(np.asarray(iq)), time.time_ns(), preview)
        return base + '.iq'

    def disconnect(self):
        try:
            self._lib.bbAbort(self.handle)
        finally:
            self._lib.bbCloseDevice(self.handle)


class BB60Mock:
    """No-hardware stand-in: writes a tiny int16 .iq + matching .xml and fires events."""
    def __init__(self, serial: int = 0, ref_level: float = -20.0,
                 decimation: int = 1, bandwidth_hz: float = 27.0e6,
                 lib_path: str | None = None):
        self._decim = int(decimation)
        self._bw = float(bandwidth_hz)
        self.ref_level = float(ref_level)
        self.scale_factor = 10 ** (-self.ref_level / 20.0)
        self.device_type = 'BB60D'
        self.serial = int(serial) or 24248018
        print(f'Connected to MOCK Signal Hound {self.device_type}, SN: {self.serial}')

    _preview = BB60._preview
    _write_xml = BB60._write_xml
    save_snippet = BB60.save_snippet

    def record(self, center_hz, seconds, base, events=None, write_preview=True, stop_event=None):
        sample_rate = 40e6 / self._decim
        count = 8
        amp = (np.random.randn(count * 2) * 0.01).astype(np.float32)
        i16 = np.clip(np.round(amp * (self.scale_factor * 32767.0)), -32768, 32767).astype('<i2')
        with open(base + '.iq', 'wb') as f:
            i16.tofile(f)
        for _t, fn in sorted(events or [], key=lambda x: x[0]):
            fn() # fire every RF/power step immediately
        epoch_ns = time.time_ns()
        preview = self._preview(amp) if write_preview else None
        self._write_xml(base, center_hz, sample_rate, count, epoch_ns, preview)
        return count, sample_rate

    def snapshot(self, center_hz, seconds):
        # simulated power: RF high in [1,4) & [6,8) s, an interference spike near 7 s
        import time as _t
        if not hasattr(self, '_t0'):
            self._t0 = _t.time()
        elapsed = _t.time() - self._t0
        high = (1 <= elapsed < 4) or (6 <= elapsed < 8)
        base_dbm = -35.0 if high else -70.0
        if 6.9 <= elapsed < 7.2:
            base_dbm = -25.0
        power_dbm = base_dbm + float(np.random.randn()) * 0.5
        n = min(4096, max(1, int(round((40e6 / self._decim) * seconds))))
        iq = (np.random.randn(n) + 1j * np.random.randn(n)).astype(np.complex64)
        return iq, 40e6 / self._decim, power_dbm

    def disconnect(self):
        pass