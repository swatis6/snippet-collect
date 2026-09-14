import yaml

from drivers.signalhound import spike, vsg60, vsg60_mock


def connect_vsg(debug: bool = False,
                mock: bool = False) -> vsg60.VSG60 | vsg60_mock.VSG60Mock:
    vsg = vsg60.VSG60(timeout=2000, debug=debug) if not mock \
        else vsg60_mock.VSG60Mock(debug=debug)
    return vsg

def connect_sa(port: int, ref_lvl: float, span: float, rbw: float,
               debug: bool) -> spike.Spike:
    analyzer = spike.Spike(port=port, timeout=2000, debug=debug)
    analyzer.switch_mode("SA")
    analyzer.set_reference_level(ref_lvl)
    analyzer.set_span(span)
    analyzer.set_RBW(rbw)
    return analyzer

class HoTERSweep():
    def __init__(self, config_path: str):
        # Load configuration from yaml file
        with open(config_path, 'r') as config_file:
            self.config = yaml.safe_load(config_file)
        self.config_vsg = self.config['vsg']
        self.config_sa = self.config['spec-an']

        # Initialize Signal Hound devices
        self.vsg = connect_vsg(self.config['debug-mode'],
                               self.config['mock-vsg'])
        try:
            self.analyzer = connect_sa(
                5025,
                self.config_sa['ref-lvl-dbm'],
                self.config_sa['freq-span-mhz']*1e6,
                self.config_sa['rbw-khz']*1e3,
                self.config['debug-mode'])
            self.analyzer.activate_marker(1, 'POS', peak_tracking=True)
            self.sa_connected = True
        except Exception as _:
            self.analyzer = None
            self.sa_connected = False
            print("Warning: No spectrum analyzer detected, continuing without sensing.")

        # Initialize data storage
        self.tx_data = [['Timestamp', 'State', 'Power (dBm)', 'Output Freq (MHz)', 'Modulation']]
        if self.sa_connected:
            self.tx_data[0] += ['Sensed Freq (MHz)', 'Sensed Power (dBm)']
