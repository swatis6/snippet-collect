# snippet-collect
Transmit &amp; IQ collection automation

## General Use

pip install numpy pyvisa pyyaml keyboard matplotlib

1. Set everything up in .yaml files
2. Run "python triggered_IQRx_config.py" on terminal 1 (server)
3. When testing, run "python tx_transmit.py" on terminal 2 (client)
4. Ctrl+C to end server in terminal 1

Util & Drivers are directly from HoTER

## Using Command line
 
### `triggered_IQRx.py` (Rx server)
 
```
python triggered_IQRx.py [--config triggered_IQRx_config.yaml] [--mock | --no-mock]
```
 
| Flag | Meaning |
|---|---|
| `--config PATH` | config file (default `triggered_IQRx_config.yaml`) |
| `--mock` / `--no-mock` | force simulated / real BB60 (overrides config) |
 
Press **ESC** to stop the server.
 
### `tx_transmit.py` (Tx client)
 
```
python tx_transmit.py [--config tx_transmit_config.yaml] [--test NAME]
                      [--tx1 625,700,850] [--tx2 1250] [--rx 1250]
                      [--mock | --no-mock] [--waterfall | --no-waterfall]
```
 
| Flag | Meaning |
|---|---|
| `--config PATH` | config file (default `tx_transmit_config.yaml`) |
| `--test NAME` | test name (folder name) |
| `--tx1 A,B,C` | comma list of Tx1 sweep freqs in MHz |
| `--tx2 MHz` | constant Tx2 freq in MHz |
| `--rx MHz` | Rx tune freq in MHz (sent to the server) |
| `--mock` / `--no-mock` | force mock / real VSG |
| `--waterfall` / `--no-waterfall` | tell the Rx to pop a live waterfall (or not) |
 
Any flag left off falls back to the YAML.
 
Examples:
 
```
python tx_transmit.py --test HWTest --tx1 625,700,850 --tx2 1250 --rx 1250
python tx_transmit.py --tx1 625 --no-waterfall            # single freq, no plot
python tx_transmit.py --mock                               # full dry run
```
 
### `waterfall.py` (plot)
 
```
python waterfall.py <folder> --live [--save PNG] [--fft 1024] [--title T]
python waterfall.py <folder> --once  [--save PNG]
python waterfall.py a.iq b.iq ...     [--save PNG]
```
 
| Form | Meaning |
|---|---|
| `<folder> --live` | watch the folder, add a row per new snippet; saves a PNG when you close the window |
| `<folder> --once` | render the folder's current snippets once, then exit |
| `a.iq b.iq ...` | render specific `.iq` files (each needs its `.xml` sidecar) |
| `--save PATH` | write a PNG instead of / in addition to showing |
| `--fft N` | FFT size per row (default 1024; larger = finer freq resolution) |
| `--title T` | window / plot title |
 
Live windows auto-save to `<folder>/<foldername>_waterfall.png` on close.


Examples:
 
```
python waterfall.py results/HWTest/625 --live
python waterfall.py results/HWTest/625 --once --save wf625.png
python waterfall.py results/HWTest/625/tx-2/625Tx1_1250Tx2_1250Rx_HWTest_4-*.iq --save one.png
```

## Output Organization

```
results/<test>/
  <test>_rx_log.csv ---> command-receive + capture times (Rx)
  <test>_tx_log.csv ---> tx segment start/end times (Tx)
  <Tx1>/ ---> one folder per Tx1 freq
    <Tx1>_waterfall.png 
    wait/<Tx1>Tx1_<Tx2>Tx2_<Rx>Rx_<test>_<n><stamp>.iq (+ .xml)
    tx-<power>/...
    recovery-<power>/...
```