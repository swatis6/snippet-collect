#!/usr/bin/env python3
"""Mock Tx client for the IQ receive server (triggered_IQRx.py).

To use -
In one terminal, start the IQ server (make sure triggered_IQRx_config.yaml has mock: true):
         python triggered_IQRx.py
In another terminal, activate client:
         python trigger_mock_tx.py            --> type begin / tx 2 / endtx / end / quit
         python trigger_mock_tx.py --auto     --> runs automatic begin/start_tx/end_tx/end demo
"""

import argparse
import json
import socket
import threading
import time


def connect(host, port, retries=20):
    for i in range(retries):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            return s
        except OSError:
            if i == 0:
                print(f'Waiting for IQ server at {host}:{port} ...')
            time.sleep(0.5)
    raise SystemExit(f'Could not connect to {host}:{port} - is triggered_IQRx.py running?')


def reader(sock): #print the server's acks
    buf = b''
    while True:
        try:
            data = sock.recv(4096)
        except OSError:
            break
        if not data:
            print('\n[server closed the connection]')
            break
        buf += data
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            if line.strip():
                print(f'   <- server: {line.decode().strip()}')


def send(sock, obj):
    sock.sendall((json.dumps(obj) + '\n').encode())
    print(f'-> sent: {json.dumps(obj)}')


def parse_command(text): #begin / tx <power> / endtx / end
    parts = text.split()
    if not parts:
        return None
    cmd = parts[0].lower()
    if cmd == 'begin':
        return {'cmd': 'begin'}
    if cmd in ('tx', 'start_tx', 'start'):
        msg = {'cmd': 'start_tx'}
        if len(parts) > 1:
            try:
                msg['power'] = float(parts[1])
            except ValueError:
                pass
        return msg
    if cmd in ('endtx', 'end_tx'):
        return {'cmd': 'end_tx'}
    if cmd in ('end', 'done', 'stop'):
        return {'cmd': 'end'}
    return None


def interactive(sock):
    print('\nCommands:')
    print('   begin          script start -> Rx "wait" state')
    print('   tx 2           tx segment at 2 dB -> Rx "tx" state')
    print('   endtx          recovery -> Rx "recovery" state')
    print('   end            script done -> stop')
    print('   quit           exit this client\n')
    while True:
        try:
            text = input('tx> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.lower() in ('quit', 'exit', 'q'):
            break
        if not text:
            continue
        msg = parse_command(text)
        if msg is None:
            print('   ? unknown - try: begin | tx 2 | endtx | end | quit')
            continue
        send(sock, msg)


def auto(sock): #begin -> (tx, endtx) x3 -> end
    print('[auto] demo: begin -> tx/endtx x3 -> end')
    send(sock, {'cmd': 'begin', 'test': 'A-off', 'tx_freq_mhz': 625, 'rx_freq_mhz': 1250})
    time.sleep(4) # wait state
    for power in (2, 4, 6):
        send(sock, {'cmd': 'start_tx', 'power': power})
        time.sleep(4) # tx state
        send(sock, {'cmd': 'end_tx'})
        time.sleep(4) # recovery state
    send(sock, {'cmd': 'end'})
    time.sleep(1)
    print('[auto] demo done')


def main():
    ap = argparse.ArgumentParser(description='Mock Tx client for the IQ receive server')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=5050)
    ap.add_argument('--auto', action='store_true', help='run a scripted demo instead of interactive')
    args = ap.parse_args()

    sock = connect(args.host, args.port)
    print(f'Connected to IQ server at {args.host}:{args.port}')
    threading.Thread(target=reader, args=(sock,), daemon=True).start()

    try:
        auto(sock) if args.auto else interactive(sock)
    finally:
        sock.close()
        print('disconnected.')


if __name__ == '__main__':
    main()