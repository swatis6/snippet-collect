from datetime import datetime as dt
import argparse
import json
import os
import socket
import time
import csv

import yaml

from util import signalhound as sh
from drivers.signalhound import vsg60, vsg60_mock


TX_HEADER = ['Rx Freq (MHz)', 'Tx1 Freq (MHz)', 'Tx2 Freq (MHz)', 'Power (dB)',
             'Start Time', 'End Time', 'Duration (s)']


def connect_server(host, port, retries=20):
    for i in range(retries):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            return s
        except OSError:
            if i == 0:
                print(f'Waiting for IQ server at {host}:{port} ...')
            time.sleep(0.5)
    raise SystemExit(f'Could not reach IQ server at {host}:{port} - is triggered_IQRx.py running?')


def send(sock, obj):
    sock.sendall((json.dumps(obj) + '\n').encode())
    print(f'-> {json.dumps(obj)}')


def run(args):
    with open(args.config, 'r') as config_file:
        config = yaml.safe_load(config_file)
    main = config['main']
    second = config['second-signal']
    srv = config['server']

    test = args.test or config['test-name']
    _now = dt.now()
    test = test + _now.strftime('-%m-%d-%y-%Hh%Mm%Ss') + f'{_now.microsecond // 1000:03d}'
    tx1_list = [float(x) for x in args.tx1.split(',')] if args.tx1 else config['tx1-freqs-mhz']
    rx_list = [float(x) for x in args.rx.split(',')] if args.rx else config['rx-freqs-mhz']
    tx2_mhz = args.tx2 if args.tx2 is not None else config['tx2-freq-mhz']
    mock = args.mock if args.mock is not None else config['mock-vsg']
    waterfall = args.waterfall if args.waterfall is not None else config['waterfall']['enabled']
    debug = config['debug-mode']
    powers = main['powers-db']
    wait_sec, tx_sec, recovery_sec = main['wait-sec'], main['tx-sec'], main['recovery-sec']
    iq_cfg = config['iq']

    tx2_msg = tx2_mhz if second['enabled'] else None

    out_base = config['output']['dir']
    out_dir = os.path.join(out_base, test)
    os.makedirs(out_dir, exist_ok=True)

    vsg = sh.connect_vsg(debug, mock)
    second_vsg = None
    if second['enabled']:
        second_vsg = vsg60_mock.VSG60Mock(debug=debug) if mock \
            else vsg60.VSG60(port=second['port'], debug=debug)

    sock = connect_server(srv['host'], srv['port'])
    print(f'Connected to IQ server at {srv["host"]}:{srv["port"]}')

    tx_rows = [TX_HEADER]

    try:
        if second_vsg is not None:
            second_vsg.set_freq(tx2_mhz * 1e6)
            second_vsg.set_power(second['power-db'])
            second_vsg.enable_rf()
            print(f'  Tx2 constant ON at {tx2_mhz} MHz')

        for rx in rx_list:
            for tx1 in tx1_list:
                tx1_off = isinstance(tx1, str) and tx1.lower() in ('off', 'no', 'none') or tx1 is None
                tx1_msg = 'off' if tx1_off else tx1
                send(sock, {'cmd': 'begin', 'test': test, 'tx1_freq_mhz': tx1_msg,
                            'tx2_freq_mhz': tx2_msg, 'rx_freq_mhz': rx,
                            'waterfall': waterfall, 'out_dir': out_base, 'iq': iq_cfg})
                if not tx1_off:
                    vsg.set_freq(tx1 * 1e6)
                vsg.disable_rf()
                print(f'Rx {rx} / Tx1 {"OFF (baseline)" if tx1_off else f"{tx1} MHz"}: wait {wait_sec} s')
                time.sleep(wait_sec)

                for power in powers:
                    if not tx1_off:
                        vsg.set_power(power)
                        vsg.enable_rf()
                    t_start = dt.now()
                    send(sock, {'cmd': 'start_tx', 'power': power})
                    print(f'  {"BASELINE (RF off)" if tx1_off else f"TX {power} dB"} for {tx_sec} s')
                    time.sleep(tx_sec)

                    vsg.disable_rf()
                    t_end = dt.now()
                    send(sock, {'cmd': 'end_tx'})
                    tx_rows.append([rx, tx1_msg, (tx2_mhz if tx2_msg is not None else 'NoTx2'), power,
                                    str(t_start), str(t_end), f'{(t_end - t_start).total_seconds():.2f}'])
                    print(f'  recovery {recovery_sec} s')
                    time.sleep(recovery_sec)

                send(sock, {'cmd': 'end'})
    finally:
        vsg.disable_rf()
        if second_vsg is not None:
            second_vsg.disable_rf()
            second_vsg.disconnect()
        vsg.disconnect()
        sock.close()
        with open(os.path.join(out_dir, f'{test}_tx_log.csv'), 'w', newline='') as f:
            csv.writer(f).writerows(tx_rows)

    print(f'Tx done. Tx log -> {os.path.join(out_dir, f"{test}_tx_log.csv")}')


def parse_args():
    ap = argparse.ArgumentParser(description='Tx transmit (Rx sweep x Tx1 sweep + constant Tx2)')
    ap.add_argument('--config', default='tx_transmit_config.yaml')
    ap.add_argument('--test')
    ap.add_argument('--tx1', help='comma list of Tx1 freqs in MHz')
    ap.add_argument('--tx2', type=float, help='Tx2 constant freq in MHz')
    ap.add_argument('--rx', help='comma list of Rx freqs in MHz')
    gm = ap.add_mutually_exclusive_group()
    gm.add_argument('--mock', dest='mock', action='store_true')
    gm.add_argument('--no-mock', dest='mock', action='store_false')
    ap.set_defaults(mock=None)
    gw = ap.add_mutually_exclusive_group()
    gw.add_argument('--waterfall', dest='waterfall', action='store_true')
    gw.add_argument('--no-waterfall', dest='waterfall', action='store_false')
    ap.set_defaults(waterfall=None)
    return ap.parse_args()


if __name__ == "__main__":
    run(parse_args())