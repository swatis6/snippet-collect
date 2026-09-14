# Triggered IQ Receive - server that captures IQ snippets based on triggers from the Tx script.
#
# Always on: opens the BB60, keeps it connected but idle, and waits for the Tx (client) to connect over TCP and 
# report its state. Receiver logs a short IQ snippet on an interval that depends on that state, so 'wait' / 'tx'
#  / 'recovery' can all have different snippet legnths and spacing
#
# Commands (messages from the Tx, JSON or simple text):
#   {"cmd": "begin", "test": "A-off", "tx_freq_mhz": 625, "rx_freq_mhz": 1250} -> script started --> enter 'wait'
#   {"cmd": "start_tx", "power": 2}   --> a tx segment started at this power --> enter 'tx'
#   {"cmd": "end_tx"}                 --> recovery started --> enter 'recovery'
#   {"cmd": "end"}                    --> script done --> stop taking snippets
#
# Organization:
# Snippets -> results/<test>/<state>/<tx>tx_<rx>rx_<n>.iq (+ .xml), e.g. A-off/tx-2/625tx_1250rx_1.iq
# CSV log -> results/<test>/<test>_rx_log.csv (command-receive times + capture-start times)

from datetime import datetime as dt
import json
import os
import socket
import threading
import time
import csv

import keyboard
import yaml

from drivers.signalhound import bb60


CONFIG_FILE = 'triggered_IQRx_config.yaml'
MAX_BW = {1: 27.0e6, 2: 17.8e6, 4: 8.0e6, 8: 3.75e6} #decimation -> max bandwidth, to check settings later
RX_HEADER = ['Time', 'Event', 'State', 'Tx Power (dB)', 'Tx Freq (MHz)', 'Rx Freq (MHz)',
             'Snippet #', 'File']


def _fmt(v): #625.0 -> '625'
    if v is None:
        return 'none'
    if isinstance(v, str):
        return v
    return str(int(v)) if float(v).is_integer() else str(v)


def _messages(conn):
    """Yield parsed command messages (JSON or 'cmd [arg]' text) from a socket line by line."""
    buf = b'' #empty buffer - data accumulates here until there's a full line
    while True:
        try:
            data = conn.recv(4096) 
        except OSError:
            break
        if not data:
            break #stop looping if data is not being transferred
        buf += data
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1) #chop off first full line, keep the rest
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line.decode()) #JSON line -> python dict
            except Exception:
                parts = line.decode().split() #if not json, read as simple text like "start_tx 2"
                msg = {'cmd': parts[0].lower()} if parts else {}
                if len(parts) > 1:
                    try:
                        msg['power'] = float(parts[1])
                    except ValueError:
                        pass
                if msg:
                    yield msg


def _ack(conn, state): #try to reply telling the Tx our current state but ok if not
    try:
        conn.sendall((json.dumps({'ack': state}) + '\n').encode())
    except OSError:
        pass


def _save_rx_csv(rows, sess, cfg): #rewrite the rx csv under the test folder
    folder = os.path.join(cfg['out_dir'], sess['test'])
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, f"{sess['test']}_rx_log.csv"), 'w', newline='') as f:
        csv.writer(f).writerows(rows)


def do_snippet(sess, state, power, analyzer, cfg, rows, lock): #get + save one snippet
    with lock:
        sess['count'] += 1
        n, tx, rx, test = sess['count'], sess['tx'], sess['rx'], sess['test']

    if state == 'tx':
        state_folder = f'tx-{_fmt(power)}' #tx-2
    elif state == 'recovery':
        state_folder = f'recovery-{_fmt(power)}' #recovery-2 (power of the tx that just ended)
    else:
        state_folder = state #wait
    folder = os.path.join(cfg['out_dir'], test, state_folder)
    os.makedirs(folder, exist_ok=True)
    fname = f'{_fmt(tx)}tx_{_fmt(rx)}rx_{n}' #625tx_1250rx_1
    base = os.path.join(folder, fname)

    center_hz = rx * 1e6
    cap_start = dt.now()
    iq, sr, power_dbm = analyzer.snapshot(center_hz, cfg['lengths'][state]) 
    analyzer.save_snippet(base, iq, center_hz, sr, False)

    rel = os.path.join(test, state_folder, fname + '.iq')
    print(f'  snippet #{n} [{state}{"" if state != "tx" else " p" + _fmt(power)}] '
          f'{power_dbm:.1f} dBm -> {rel}')
    with lock:
        rows.append([str(cap_start), 'snippet', state, power, tx, rx, n, rel])
    _save_rx_csv(rows, sess, cfg)


def handle_client(conn, addr, analyzer, cfg):
    print(f'Tx connected from {addr[0]}:{addr[1]}')
    sess = {'state': 'idle', 'power': None, 'test': cfg['test'],
            'tx': cfg['tx_freq_mhz'], 'rx': cfg['rx_freq_mhz'], 'count': 0, 'closed': False}
    rows = [RX_HEADER] #rx csv rows (command receives + snippet captures)
    lock = threading.Lock() #one thread touches the notepad at a time

    def log_cmd(cmd, trecv): #record the time a command was received
        with lock:
            rows.append([str(trecv), f'cmd:{cmd}', sess['state'], sess['power'],
                         sess['tx'], sess['rx'], '', ''])
        _save_rx_csv(rows, sess, cfg)

    def reader(): #recieves the Tx state changes and updates shared notepad
        for msg in _messages(conn):
            cmd = str(msg.get('cmd', '')).lower()
            trecv = dt.now()
            if cmd == 'begin': #script started --> wait time
                with lock:
                    sess['test'] = msg.get('test', cfg['test'])
                    sess['tx'] = msg.get('tx_freq_mhz', cfg['tx_freq_mhz'])
                    sess['rx'] = msg.get('rx_freq_mhz', cfg['rx_freq_mhz'])
                    sess['state'], sess['count'], sess['power'] = 'wait', 0, None
                log_cmd('begin', trecv)
                _ack(conn, 'wait')
            elif cmd == 'start_tx': #tx started at a power --> tx
                with lock:
                    sess['power'], sess['state'] = msg.get('power'), 'tx'
                log_cmd('start_tx', trecv)
                _ack(conn, 'tx')
            elif cmd == 'end_tx': #recovery started -> recovery
                with lock:
                    sess['state'] = 'recovery'
                log_cmd('end_tx', trecv)
                _ack(conn, 'recovery')
            elif cmd == 'end': #script done -> stop
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

        if state != last_state: #state just changed
            if state in ('wait', 'tx', 'recovery'):
                print(f'  state={state} - snippet every {cfg["intervals"][state]:g} s')
                next_cap = now 
            last_state = state

        if state in ('wait', 'tx', 'recovery') and now >= next_cap:
            do_snippet(sess, state, power, analyzer, cfg, rows, lock)
            next_cap = now + cfg['intervals'][state]

        time.sleep(0.02)

    _save_rx_csv(rows, sess, cfg) #final save
    print(f'Tx {addr[0]}:{addr[1]} disconnected ({sess["count"]} snippets)')


def run():
    #pull config ---
    with open(CONFIG_FILE, 'r') as config_file:
        config = yaml.safe_load(config_file)
    rx = config['rx']
    snip = config['snippet']
    srv_cfg = config['server']
    out = config['output']
    test = config['test-name']

    rx_freq_mhz = rx['rx-freq-mhz']
    tx_freq_mhz = rx['tx-freq-mhz']

    #just in case ---
    assert 0 < rx_freq_mhz <= config['max-freq-mhz'], \
        f"rx freq {rx_freq_mhz} MHz outside 0..{config['max-freq-mhz']} MHz"
    dec = rx['decimation']
    if dec in MAX_BW:
        assert rx['if-bandwidth-hz'] <= MAX_BW[dec], \
            f"if-bandwidth {rx['if-bandwidth-hz']/1e6:g} MHz exceeds max " \
            f"{MAX_BW[dec]/1e6:g} MHz at decimation {dec}"

    #connect BB60 once, then it stays connected and idle for the life of the server ---
    is_mock = config['mock']
    BB = bb60.BB60Mock if is_mock else bb60.BB60
    analyzer = BB(rx['serial'], rx['ref-lvl-dbm'], dec, rx['if-bandwidth-hz'], rx['bb-api-lib'])

    cfg = {'rx_freq_mhz': rx_freq_mhz, 'tx_freq_mhz': tx_freq_mhz, 'test': test,
           'out_dir': out['dir'],
           'lengths': {s: snip[s]['length-sec'] for s in ('wait', 'tx', 'recovery')},
           'intervals': {s: snip[s]['interval-sec'] for s in ('wait', 'tx', 'recovery')}}

    #serve ---
    host, port = srv_cfg['host'], srv_cfg['port']
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #create TCP socket
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #reuse the port right after a restart
    server.bind((host, port)) #claim the address + port
    server.listen(1)
    server.settimeout(0.5) #half-second timeout so we can check for the ESC key
    print(f'IQ server ready on {host}:{port} - BB60 idle, waiting for Tx. (ESC to quit)')

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


if __name__ == "__main__":
    run()