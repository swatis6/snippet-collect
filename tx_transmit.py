# Tx transmit - main (f0) signal multi-power sweep & sometimes a constant 2f0 signal.
#
# Timeline: 

# send 'begin' -> wait-sec (Rx 'wait') 
# for each power: 
#   set power, 
#   RF on, 
#   send 'start_tx' (Rx 'tx'), 
#   transmit tx-sec, 
#   RF off, 
#   send 'end_tx' (Rx 'recovery'),
#   recovery-sec 
# send 'end'. 
# 
# A second signal at 2*f0 can be left on all the way through
# Logs times and such to a csv.

from datetime import datetime as dt
import json
import os
import socket
import time
import csv

import yaml

from util import signalhound as sh
from drivers.signalhound import vsg60, vsg60_mock


CONFIG_FILE = 'tx_transmit_config.yaml'
TX_HEADER = ['Power (dB)', 'Tx Freq (MHz)', 'Start Time', 'End Time', 'Duration (s)']


def connect_server(host, port, retries=20): #open the link to the IQ server, retry while it comes up
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


def send(sock, obj): #one command to the server as newline-terminated JSON
    sock.sendall((json.dumps(obj) + '\n').encode())
    print(f'-> {json.dumps(obj)}')


def run():
    #pull config ---
    with open(CONFIG_FILE, 'r') as config_file:
        config = yaml.safe_load(config_file)
    main = config['main']
    second = config['second-signal']
    srv = config['server']

    test = config['test-name']
    tx_mhz = config['tx-freq-mhz']
    rx_mhz = config['rx-freq-mhz']
    powers = main['powers-db']
    wait_sec, tx_sec, recovery_sec = main['wait-sec'], main['tx-sec'], main['recovery-sec']
    mock = config['mock-vsg']
    debug = config['debug-mode']

    out_dir = os.path.join(config['output']['dir'], test)
    os.makedirs(out_dir, exist_ok=True)

    #connect the VSG (main signal) and, if enabled, a second VSG ---
    vsg = sh.connect_vsg(debug, mock)
    second_vsg = None
    if second['enabled']:
        second_vsg = vsg60_mock.VSG60Mock(debug=debug) if mock \
            else vsg60.VSG60(port=second['port'], debug=debug)

    #connect the IQ server ---
    sock = connect_server(srv['host'], srv['port'])
    print(f'Connected to IQ server at {srv["host"]}:{srv["port"]}')

    tx_rows = [TX_HEADER] #tx csv rows (one per tx bit)

    try:
        #tell the server we are starting
        send(sock, {'cmd': 'begin', 'test': test, 'tx_freq_mhz': tx_mhz, 'rx_freq_mhz': rx_mhz})

        #second signal
        if second_vsg is not None:
            second_vsg.set_freq(second['freq-mult'] * tx_mhz * 1e6)
            second_vsg.set_power(second['power-db'])
            second_vsg.enable_rf()
            print(f'  2nd signal ON at {second["freq-mult"] * tx_mhz} MHz')

        vsg.set_freq(tx_mhz * 1e6) #main signal freq (Hz)
        vsg.disable_rf()

        #wait time at the beginning
        print(f'  wait {wait_sec} s')
        time.sleep(wait_sec)

        #for each power: transmit, then recovery
        for power in powers:
            vsg.set_power(power)
            vsg.enable_rf()
            t_start = dt.now()
            send(sock, {'cmd': 'start_tx', 'power': power})
            print(f'  TX {power} dB for {tx_sec} s')
            time.sleep(tx_sec)

            vsg.disable_rf()
            t_end = dt.now()
            send(sock, {'cmd': 'end_tx'})
            tx_rows.append([power, tx_mhz, str(t_start), str(t_end),
                            f'{(t_end - t_start).total_seconds():.2f}'])

            print(f'  recovery {recovery_sec} s')
            time.sleep(recovery_sec)

        send(sock, {'cmd': 'end'})
    finally:
        #everything off + save the tx sheet
        vsg.disable_rf()
        if second_vsg is not None:
            second_vsg.disable_rf()
            second_vsg.disconnect()
        vsg.disconnect()
        sock.close()
        with open(os.path.join(out_dir, f'{test}_tx_log.csv'), 'w', newline='') as f:
            csv.writer(f).writerows(tx_rows)

    print(f'Tx done. Tx log -> {os.path.join(out_dir, f"{test}_tx_log.csv")}')


if __name__ == "__main__":
    run()