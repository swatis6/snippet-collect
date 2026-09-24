# Triggered IQ Receive - server that captures IQ snippets based on triggers from the Tx script.
#
# Always on: opens the BB60, keeps it connected but idle, and waits for the Tx (client) to
# connect over TCP and report its state + all test info. Snippet length/spacing depends on
# state ('wait' / 'tx' / 'recovery'). Rx holds ONLY IQ settings; everything else comes from Tx.
#
# Commands (from the Tx, JSON or simple text):
#   {"cmd":"begin","test":"HWTest","tx1_freq_mhz":625,"tx2_freq_mhz":1250,"rx_freq_mhz":1250,"waterfall":true}
#   {"cmd":"start_tx","power":2}  --> tx segment at this power --> 'tx'
#   {"cmd":"end_tx"}              --> recovery --> 'recovery'
#   {"cmd":"end"}                --> stop snippets (idle)
# (tx2_freq_mhz null/absent -> "NoTx2" in filenames. A new 'begin' = a new Tx1 step.)
#
# Files: results/<test>/<tx1>/<state>/<Tx1>Tx1_<Tx2>Tx2_<Rx>Rx_<test>_<n><spike-stamp>.iq (+ .xml)
# CSV:   results/<test>/<test>_rx_log.csv

from datetime import datetime as dt
import argparse
import json
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


MAX_BW = {1: 27.0e6, 2: 17.8e6, 4: 8.0e6, 8: 3.75e6}
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


def _messages(conn):
    """Yield parsed command messages (JSON or 'cmd [arg]' text) from a socket line by line."""
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


def _spawn_waterfall(test, tx1, cfg):
    folder = os.path.join(cfg['out_dir'], test, _fmt(tx1))
    os.makedirs(folder, exist_ok=True)
    wf = os.path.join(HERE, 'waterfall.py')
    try:
        return subprocess.Popen([sys.executable, wf, folder, '--live',
                                 '--title', f'{test}  Tx1={_fmt(tx1)} MHz'])
    except Exception as e:
        print(f'  (waterfall launch failed: {e})')
        return None


def do_snippet(sess, state, power, analyzer, cfg, rows, lock):
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
    folder = os.path.join(cfg['out_dir'], test, _fmt(tx1), state_folder)
    os.makedirs(folder, exist_ok=True)

    tx2_label = f'{_fmt(tx2)}Tx2' if tx2 is not None else 'NoTx2'
    now = dt.now()
    fname = f'{_fmt(tx1)}Tx1_{tx2_label}_{_fmt(rx)}Rx_{test}_{n}' + _spike_stamp(now)
    base = os.path.join(folder, fname)

    center_hz = rx * 1e6
    iq, sr, power_dbm = analyzer.snapshot(center_hz, cfg['lengths'][state])
    analyzer.save_snippet(base, iq, center_hz, sr, False)

    rel = os.path.join(test, _fmt(tx1), state_folder, fname + '.iq')
    print(f'  snippet #{n} [{state}{"" if state != "tx" else " p" + _fmt(power)}] '
          f'{power_dbm:.1f} dBm -> {rel}')
    with lock:
        rows.append([str(now), 'snippet', state, power, tx1, tx2, rx, n, rel])
    _save_rx_csv(rows, sess, cfg)


def handle_client(conn, addr, analyzer, cfg):
    print(f'Tx connected from {addr[0]}:{addr[1]}')
    sess = {'state': 'idle', 'power': None, 'test': 'test',
            'tx1': None, 'tx2': None, 'rx': None, 'waterfall': False,
            'count': 0, 'closed': False}
    rows = [RX_HEADER]
    procs = []
    lock = threading.Lock()

    def log_cmd(cmd, trecv):
        with lock:
            rows.append([str(trecv), f'cmd:{cmd}', sess['state'], sess['power'],
                         sess['tx1'], sess['tx2'], sess['rx'], '', ''])
        _save_rx_csv(rows, sess, cfg)

    def reader(): #receives Tx state changes + test info, updates shared notepad
        for msg in _messages(conn):
            cmd = str(msg.get('cmd', '')).lower()
            trecv = dt.now()
            if cmd == 'begin': #new Tx1 step --> wait
                with lock:
                    sess['test'] = msg.get('test', sess['test'])
                    sess['tx1'] = msg.get('tx1_freq_mhz')
                    sess['tx2'] = msg.get('tx2_freq_mhz')
                    sess['rx'] = msg.get('rx_freq_mhz')
                    sess['waterfall'] = bool(msg.get('waterfall', False))
                    sess['state'], sess['count'], sess['power'] = 'wait', 0, None
                    test_i, tx1_i, wf_i = sess['test'], sess['tx1'], sess['waterfall']
                log_cmd('begin', trecv)
                if wf_i:
                    p = _spawn_waterfall(test_i, tx1_i, cfg)
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

    last_state, next_cap = None, 0.0
    while not sess['closed']:
        with lock:
            state, power = sess['state'], sess['power']
        now = time.time()

        if state != last_state:
            if state in ('wait', 'tx', 'recovery'):
                if cfg['enabled'][state]:
                    print(f'  state={state} - snippet every {cfg["intervals"][state]:g} s')
                    next_cap = now
                else:
                    print(f'  state={state} - capture off')
            last_state = state

        if state in ('wait', 'tx', 'recovery') and cfg['enabled'][state] and now >= next_cap:
            do_snippet(sess, state, power, analyzer, cfg, rows, lock)
            next_cap = now + cfg['intervals'][state]

        time.sleep(0.02)

    _save_rx_csv(rows, sess, cfg)
    print(f'Tx {addr[0]}:{addr[1]} disconnected ({sess["count"]} snippets)')


def run(args):
    with open(args.config, 'r') as config_file:
        config = yaml.safe_load(config_file)
    rx = config['rx']
    snip = config['snippet']
    srv_cfg = config['server']
    out = config['output']

    dec = rx['decimation']
    if dec in MAX_BW:
        assert rx['if-bandwidth-hz'] <= MAX_BW[dec], \
            f"if-bandwidth {rx['if-bandwidth-hz']/1e6:g} MHz exceeds max " \
            f"{MAX_BW[dec]/1e6:g} MHz at decimation {dec}"


    is_mock = args.mock if args.mock is not None else config['mock']
    BB = bb60.BB60Mock if is_mock else bb60.BB60
    analyzer = BB(rx['serial'], rx['ref-lvl-dbm'], dec, rx['if-bandwidth-hz'], rx['bb-api-lib'])

    cfg = {'out_dir': out['dir'],
           'lengths': {s: snip[s]['length-sec'] for s in ('wait', 'tx', 'recovery')},
           'intervals': {s: snip[s]['interval-sec'] for s in ('wait', 'tx', 'recovery')},
           'enabled': {s: snip[s].get('enabled', True) for s in ('wait', 'tx', 'recovery')}}

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
    g.add_argument('--mock', dest='mock', action='store_true', help='force simulated BB60')
    g.add_argument('--no-mock', dest='mock', action='store_false', help='force real BB60')
    ap.set_defaults(mock=None)
    return ap.parse_args()


if __name__ == "__main__":
    run(parse_args())