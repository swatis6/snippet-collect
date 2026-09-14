import abc
import pyvisa as visa
import time


VISA_RM = visa.ResourceManager()


class Instrument(abc.ABC):
    def __init__(self, resource_name: str, timeout: int = 100000,
                 debug: bool = False):
        self.debug = debug
        try:
            self.inst = VISA_RM.open_resource(resource_name)
            
            # Set timeout value
            self.inst.set_visa_attribute(
                visa.constants.VI_ATTR_TMO_VALUE, timeout)
            self.inst.encoding = 'ascii'
            # Suppress end on reads
            self.inst.suppress_end_on_read = True
        except visa.errors.VisaIOError as _:
            print(f"Device not found on {resource_name}.")

    def _write(self, command):
        """Send a command to the instrument."""
        if self.debug:
            print(f'WRITE > {command}')
        self.inst.write(command)

    def _query(self, command) -> str:
        """Send a query to the instrument and return the response."""
        if self.debug:
            print(f'QUERY > {command}')
        self.inst.write(command)
        # time.sleep(0.1)
        return self.inst.read()
    
    def _query_binary(self, command) -> str:
        """Send a query to the instrument and return the binary response."""
        if self.debug:
            print(f'QUERY BINARY > {command}')
        self.inst.write(command)
        time.sleep(0.1)
        return self.inst.read_binary_values()
    
    def _query_raw(self, command):
        if self.debug:
            print(f'QUERY RAW > {command}')
        self.inst.write(command)
        response = ''
        while(response == ''):
            response = self.inst.read_raw()
        return response
    
    def _close(self):
        """Close the connection to the instrument."""
        self.inst.close()
    
    def get_id(self) -> str:
        """Get the instrument ID."""
        return self._query('*IDN?')
    
    def reset(self):
        """Reset the instrument."""
        return self._write('*RST')


def get_resources():
    return VISA_RM.list_resources()
