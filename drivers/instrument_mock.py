import abc
import time


class InstrumentMock(abc.ABC):
    def __init__(self, resource_name: str, timeout: int = 100000,
                 debug: bool = False):
        self.debug = debug
        
        (vendor, device, sn, _) = ['MockVendor', 'MockInstrument', '1234567', '']
        print(f'Connected to {vendor} {device}, SN: {sn}')

    def _write(self, command):
        """Send a command to the instrument."""
        if self.debug:
            print(f'WRITE > {command}')
        print(command)

    def _query(self, command) -> str:
        """Send a query to the instrument and return the response."""
        if self.debug:
            print(f'QUERY > {command}')
        print(command)
        time.sleep(0.1)
        return ''
    
    def _query_binary(self, command) -> str:
        """Send a query to the instrument and return the binary response."""
        if self.debug:
            print(f'QUERY BINARY > {command}')
        print(command)
        time.sleep(0.1)
        return ''
    
    def _close(self):
        """Close the connection to the instrument."""
        pass
    
    def get_id(self) -> str:
        """Get the instrument ID."""
        return self._query('*IDN?')
    
    def reset(self):
        """Reset the instrument."""
        print('*RST')


def get_resources():
    pass
