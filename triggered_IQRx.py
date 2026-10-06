from datetime import datetime as dt
import argparse
import json
import math
import os
import socket
import subprocess
import sys
import threading
import time
import csv

import keyboard
import yaml

from drivers.signalhound import bb60


# BB60 IQ max IF bandwidth per decimation (approx; bandwidth available ~0.8 x sample rate).
MAX_BW = {1: 27.0e6, 2: 17.8e6, 4: 8.0e6, 8: 3.75e6}
for _n in range(4, 14):
    MAX_BW[2 ** _n] = 0.8 * (40e6 / 2 ** _n)
NFFT_REF = 1024
RX_HEADER = ['Time', 'Event', 'State', 'Tx Power (dB)', 'Tx1 Freq (MHz)', 'Tx2 Freq (MHz)',
             'Rx Freq (MHz)', 'Snippet #', 'File']
HERE = os.path.dirname(os.path.abspath(__file__))


def _fmt(v):
    if v is None:
        return 'none'
    if isinstance(v, str):
        return v
    return str(int(v)) if float(v).is_integer() else str(v)


def _spike_stamp(now):
    return now.strftime('-%m-%d-%y-%Hh%Mm%Ss') + f'{now.microsecond // 1000:03d}'


def _rate_to_decim(sr_hz):
    decim = max(1, round(40e6 / float(sr_hz)))
    n = min(13, max(0, round(math.log2(decim))))   # ladder is 40e6 / 2^n, n = 0..13
    decim = 2 ** n
    return decim, 40e6 / decim


def _messages(conn):
    buf = b''
    while True:
        try:
            data = conn.recv(4096)
        except OSError:
            break
        if not data:
            break
        buf += data
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line.decode())
            except Exception:
                parts = line.decode().split()
                msg = {'cmd': parts[0].lower()} if parts else {}
                if len(parts) > 1:
                    try:
                        msg['power'] = float(parts[1])
                    except ValueError:
                        pass
                if msg:
                    yield msg


def _ack(conn, state):
    try:
        conn.sendall((json.dumps({'ack': state}) + '\n').encode())
    except OSError:
        pass


def _save_rx_csv(rows, sess, cfg):
    folder = os.path.join(cfg['out_dir'], sess['test'])
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, f"{sess['test']}_rx_log.csv"), 'w', newline='') as f:
        csv.writer(f).writerows(rows)


def _spawn_waterfall(test, rx, tx1, cfg):
    folder = os.path.join(cfg['out_dir'], test, _fmt(rx), _fmt(tx1))
    os.makedirs(folder, exist_ok=True)
    wf = os.path.join(HERE, 'waterfall.py')
    try:
        return subprocess.Popen([sys.executable, wf, folder, '--live',
                                 '--title', f'{test}  Rx={_fmt(rx)}  Tx1={_fmt(tx1)} MHz'])
    except Exception as e:
        print(f'  (waterfall launch failed: {e})')
        return None


def _apply_iq(iq, analyzer, sess):
    if 'sample-rate-hz' in iq:
        req_hz = float(iq['sample-rate-hz'])
    else:
        req_hz = float(iq.get('sample-rate-msps', 40)) * 1e6   # back-compat
    decim, actual = _rate_to_decim(req_hz)
    if abs(actual - req_hz) > 1.0:
        print(f'  WARNING: sample-rate {req_hz:g} Hz not a valid Signal Hound rate '
              f'(40e6/2^n); using {actual:g} Hz')
    sr = actual
    bw = float(iq.get('if-bw-mhz', 27)) * 1e6
    maxbw = MAX_BW.get(decim)
    if maxbw and bw > maxbw:
        print(f'  WARNING: IF BW {bw/1e6:g} MHz exceeds max {maxbw/1e6:g} MHz at {actual/1e6:g} MS/s; clamping')
        bw = maxbw
    analyzer.reconfigure(ref_level=iq.get('ref-lvl-dbm', -20), decimation=decim, bandwidth_hz=bw)

    phases = iq.get('phases', {})
    lengths, intervals, enabled, modes = {}, {}, {}, {}
    for st in ('wait', 'tx', 'recovery'):
        p = phases.get(st, {})
        lengths[st] = p.get('length-sec', 0.001)
        intervals[st] = p.get('interval-sec', 1)
        enabled[st] = p.get('enabled', True)
        modes[st] = str(p.get('mode', 'snippet')).lower()
        if enabled[st] and lengths[st] >= intervals[st]:
            print(f"  WARNING: '{st}' length {lengths[st]:g}s >= interval {intervals[st]:g}s "
                  f"- snippets will overlap/overrun")
        nsamp = lengths[st] * sr
        if enabled[st] and nsamp < NFFT_REF:
            print(f"  WARNING: '{st}' snippet is {nsamp:.0f} samples < FFT size {NFFT_REF} "
                  f"(length {lengths[st]:g}s at {actual/1e6:g} MS/s) - low frequency resolution")
    sess['sr'] = sr
    sess['lengths'], sess['intervals'], sess['enabled'], sess['modes'] = lengths, intervals, enabled, modes


def do_continuous(sess, state, power, analyzer, cfg, rows, lock, stop_event):
    with lock:
        sess['count'] += 1
        n = sess['count']
        tx1, tx2, rx, test = sess['tx1'], sess['tx2'], sess['rx'], sess['test']
    if rx is None:
        return

    if state == 'tx':
        state_folder = f'tx-{_fmt(power)}'
    elif state == 'recovery':
        state_folder = f'recovery-{_fmt(power)}'
    else:
        state_folder = state
    folder = os.path.join(cfg['out_dir'], test, _fmt(rx), _fmt(tx1), state_folder)
    os.makedirs(folder, exist_ok=True)

    tx2_label = f'{_fmt(tx2)}Tx2' if tx2 is not None else 'NoTx2'
    now = dt.now()
    fname = f'{_fmt(tx1)}Tx1_{tx2_label}_{_fmt(rx)}Rx_{test}_{n}' + _spike_stamp(now)
    base = os.path.join(folder, fname)
    rel = os.path.join(test, _fmt(rx), _fmt(tx1), state_folder, fname + '.iq')
    print(f'  continuous #{n} [{state}{"" if state != "tx" else " p" + _fmt(power)}] '
          f'recording -> {rel} (until phase ends)')

    count, sr = analyzer.record(rx * 1e6, None, base, write_preview=False, stop_event=stop_event)
    with lock:
        rows.append([str(now), 'continuous', state, power, tx1, tx2, rx, n, rel])
    _save_rx_csv(rows, sess, cfg)
    print(f'  continuous #{n} [{state}] done ({count} samples)')


def do_snippet(sess, state, power, analyzer, cfg, rows, lock):
    with lock:
        sess['count'] += 1
        n = sess['count']
        tx1, tx2, rx, test = sess['tx1'], sess['tx2'], sess['rx'], sess['test']
        length = sess['lengths'][state]
        interval = sess['intervals'][state]
    if rx is None:
        return

    if state == 'tx':
        state_folder = f'tx-{_fmt(power)}'
    elif state == 'recovery':
        state_folder = f'recovery-{_fmt(power)}'
    else:
        state_folder = state
    folder = os.path.join(cfg['out_dir'], test, _fmt(rx), _fmt(tx1), state_folder)
    os.makedirs(folder, exist_ok=True)

    tx2_label = f'{_fmt(tx2)}Tx2' if tx2 is not None else 'NoTx2'
    now = dt.now()
    fname = f'{_fmt(tx1)}Tx1_{tx2_label}_{_fmt(rx)}Rx_{test}_{n}' + _spike_stamp(now)
    base = os.path.join(folder, fname)

    center_hz = rx * 1e6
    t0 = time.time()
    iq, sr, power_dbm = analyzer.snapshot(center_hz, length)
    analyzer.save_snippet(base, iq, center_hz, sr, False)
    took = time.time() - t0
    if took > interval:
        print(f"  WARNING: '{state}' capture took {took:.2f}s > interval {interval:g}s "
              f"- next snippet delayed")

    rel = os.path.join(test, _fmt(rx), _fmt(tx1), state_folder, fname + '.iq')
    print(f'  snippet #{n} [{state}{"" if state != "tx" else " p" + _fmt(power)}] '
          f'{power_dbm:.1f} dBm -> {rel}')
    with lock:
        rows.append([str(now), 'snippet', state, power, tx1, tx2, rx, n, rel])
    _save_rx_csv(rows, sess, cfg)


def handle_client(conn, addr, analyzer, cfg):
    print(f'Tx connected from {addr[0]}:{addr[1]}')
    sess = {'state': 'idle', 'power': None, 'test': 'test',
            'tx1': None, 'tx2': None, 'rx': None, 'waterfall': False, 'sr': 40e6,
            'lengths': {'wait': 0.001, 'tx': 0.001, 'recovery': 0.001},
            'intervals': {'wait': 1, 'tx': 1, 'recovery': 1},
            'enabled': {'wait': True, 'tx': True, 'recovery': True},
            'modes': {'wait': 'snippet', 'tx': 'snippet', 'recovery': 'snippet'},
            'count': 0, 'closed': False}
    rows = [RX_HEADER]
    procs = []
    lock = threading.Lock()

    def log_cmd(cmd, trecv):
        with lock:
            rows.append([str(trecv), f'cmd:{cmd}', sess['state'], sess['power'],
                         sess['tx1'], sess['tx2'], sess['rx'], '', ''])
        _save_rx_csv(rows, sess, cfg)

    def reader():
        for msg in _messages(conn):
            cmd = str(msg.get('cmd', '')).lower()
            trecv = dt.now()
            if cmd == 'begin':
                with lock:
                    sess['test'] = msg.get('test', sess['test'])
                    sess['tx1'] = msg.get('tx1_freq_mhz')
                    sess['tx2'] = msg.get('tx2_freq_mhz')
                    sess['rx'] = msg.get('rx_freq_mhz')
                    sess['waterfall'] = bool(msg.get('waterfall', False))
                    cfg['out_dir'] = msg.get('out_dir', cfg['out_dir'])
                    sess['state'], sess['count'], sess['power'] = 'wait', 0, None
                    if 'iq' in msg:
                        _apply_iq(msg['iq'], analyzer, sess)
                    test_i, rx_i, tx1_i, wf_i = sess['test'], sess['rx'], sess['tx1'], sess['waterfall']
                log_cmd('begin', trecv)
                if wf_i:
                    p = _spawn_waterfall(test_i, rx_i, tx1_i, cfg)
                    if p:
                        procs.append(p)
                _ack(conn, 'wait')
            elif cmd == 'start_tx':
                with lock:
                    sess['power'], sess['state'] = msg.get('power'), 'tx'
                log_cmd('start_tx', trecv)
                _ack(conn, 'tx')
            elif cmd == 'end_tx':
                with lock:
                    sess['state'] = 'recovery'
                log_cmd('end_tx', trecv)
                _ack(conn, 'recovery')
            elif cmd == 'end':
                with lock:
                    sess['state'] = 'idle'
                log_cmd('end', trecv)
                _ack(conn, 'idle')
        sess['closed'] = True

    threading.Thread(target=reader, daemon=True).start()

    last_state, next_cap, phase_stop = None, 0.0, None
    while not sess['closed']:
        with lock:
            state, power = sess['state'], sess['power']
            enabled, intervals, modes = sess['enabled'], sess['intervals'], sess['modes']
        now = time.time()

        if state != last_state:
            if phase_stop is not None:        # leaving a phase: stop any running continuous capture
                phase_stop.set()
                phase_stop = None
            if state in ('wait', 'tx', 'recovery'):
                if not enabled[state]:
                    print(f'  state={state} - capture off')
                elif modes[state] == 'continuous':
                    print(f'  state={state} - continuous (one file for the whole phase)')
                    phase_stop = threading.Event()
                    threading.Thread(target=do_continuous,
                                     args=(sess, state, power, analyzer, cfg, rows, lock, phase_stop),
                                     daemon=True).start()
                else:
                    print(f'  state={state} - snippet every {intervals[state]:g} s')
                    next_cap = now
            last_state = state

        if (state in ('wait', 'tx', 'recovery') and enabled[state]
                and modes[state] != 'continuous' and now >= next_cap):
            do_snippet(sess, state, power, analyzer, cfg, rows, lock)
            next_cap = now + intervals[state]

        time.sleep(0.02)

    if phase_stop is not None:
        phase_stop.set()

    _save_rx_csv(rows, sess, cfg)
    print(f'Tx {addr[0]}:{addr[1]} disconnected ({sess["count"]} snippets)')


def run(args):
    with open(args.config, 'r') as config_file:
        config = yaml.safe_load(config_file)
    rx = config['rx']
    srv_cfg = config['server']
    out = config['output']

    is_mock = args.mock if args.mock is not None else config['mock']
    BB = bb60.BB60Mock if is_mock else bb60.BB60
    analyzer = BB(rx['serial'], -20.0, 1, 27.0e6, rx['bb-api-lib'])

    cfg = {'out_dir': out['dir']}

    host, port = srv_cfg['host'], srv_cfg['port']
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(1)
    server.settimeout(0.5)
    print(f'IQ server ready on {host}:{port} [{"MOCK" if is_mock else "REAL"}] - '
          f'BB60 idle, waiting for Tx. (ESC to quit)')

    try:
        while True:
            if keyboard.is_pressed('esc'):
                break
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            with conn:
                handle_client(conn, addr, analyzer, cfg)
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        analyzer.disconnect()
    print('IQ server stopped.')


def parse_args():
    ap = argparse.ArgumentParser(description='Triggered IQ receive server')
    ap.add_argument('--config', default='triggered_IQRx_config.yaml')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--mock', dest='mock', action='store_true')
    g.add_argument('--no-mock', dest='mock', action='store_false')
    ap.set_defaults(mock=None)
    return ap.parse_args()


if __name__ == "__main__":
    run(parse_args())