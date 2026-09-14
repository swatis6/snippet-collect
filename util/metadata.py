EMPTY_METADATA_JSON = {
    "test_name": None,
    "start_time": None,
    "end_time": None,
    "test_time": None,
    "devices": {
        "vsg": None,
        "tx_analyzer": None,
        "rx_analyzer": None
    },
    "vsg": {
        "power_dbm": None,
        "frequency_mhz": None,
        "on_time_sec": None,
        "off_time_sec": None,
        # "modulation": {
        #     "type": None,
        #     "mod_frequency_khz": None,
        #     "duty_cycle": None
        # }
    },
    "tx_analyzer": {
        "measurement_type": None,
        "center_frequency_mhz": None,
        "frequency_span_mhz": None,
        "reference_level_dbm": None,
        "rbw_khz": None
    },
    "rx_analyzer": {
        "measurement_type": None,
        "center_frequency_mhz": None,
        "frequency_span_mhz": None,
        "reference_level_dbm": None,
        "rbw_khz": None,
        "sidebands": {
            "offset_khz": None,
            "bandwidth_khz": None
        }
    }
}
