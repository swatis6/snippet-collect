# snippet-collect
Transmit &amp; IQ collection automation

## General Use

pip install numpy pyvisa pyyaml keyboard matplotlib tkinterdnd2

1. Set everything up in .yaml files
2. Run "python triggered_IQRx_config.py" on terminal 1 (server)
3. When testing, run "python tx_transmit.py" on terminal 2 (client)
4. Ctrl+C/esc to end server in terminal 1
5. Use waterfall_dnd.py for post-processing

Util & Drivers are directly from HoTER
Real BB60 capture needs Signal Hound's `bb_api.dll` on the path, and Spike closed.

## Command line

**Rx server**
```
python triggered_IQRx.py [--config FILE] [--mock | --no-mock]
```
ESC stops the server.

**Tx client**
```
python tx_transmit.py [--config FILE] [--test NAME]
                      [--rx 1250,1750] [--tx1 625,700,850] [--tx2 1250]
                      [--mock | --no-mock] [--waterfall | --no-waterfall]
```
Anything omitted falls back to YAML.

**Waterfall dnd**
```
python waterfall_dnd.py                    # window; drag .iq files or a folder in
python waterfall_dnd.py file.iq            # or pass files / a folder
python waterfall_dnd.py <folder> [--fft N] [--overlap F] [--no-labels] [--save PNG]
```

Output lands in `results/<test>/<rx>/<tx1>/<state>/`.