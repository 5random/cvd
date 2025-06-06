import serial
import serial.tools.list_ports
import time
from typing import List, Optional
from src.utils.config_utils.config_service import get_config_service
from src.utils.log_utils.log_service import info, warning, error

def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        info(f"Port: {port.device}")
        info(f" Description: {port.description}")
        info(f" HWID: {port.hwid}")

def find_arduino_port() -> Optional[str]:
    ports = serial.tools.list_ports.comports()
    for port in ports:
        vid = getattr(port, 'vid', None)
        description = (port.description or "").lower()
        if vid == 0x2341 or 'arduino' in description or "ch340" in description:
            return port.device
    # fallback to port from config for arduino_tc_board sensors
    try:
        config_service = get_config_service()
        if config_service:
            entries = config_service.get_sensor_configs('arduino_tc_board')
            for _, cfg in entries:
                port_name = cfg.get('port')
                if port_name:
                    return port_name
        else:
            warning("Configuration service not initialized, skipping port fallback")
    except Exception as e:
        warning(f"Error retrieving Arduino port from config: {e}")
    return None

class ArduinoTCBoardSerial:
    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connection = None

    def connect(self):
        self.connection = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        time.sleep(2)  # wait for Arduino to initialize
        info(f"Connected to Arduino on port {self.port}")

    def disconnect(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
        info(f"Disconnected from Arduino on port {self.port}")

    def _send_command(self, command: str) -> str:
        if not self.connection or not self.connection.is_open:
            error("Serial connection not established.")
            raise ConnectionError("Serial connection not established.")
        self.connection.write(f"{command}\n".encode())
        return self.connection.readline().decode().strip()

    def configure_sensors(self, indices: List[int]) -> str:
        """
        Configure temperature sensors using index-based values (0–7).
        """
        str_indices = [str(i) for i in indices]
        command = f"S,{','.join(str_indices)}"
        return self._send_command(command)

    def read_temperature(self, sensor_index: int) -> float:
        response = self._send_command(f"R{sensor_index}")
        if response == "ERR":
            raise ValueError(f"Sensor index {sensor_index} is not valid or not configured.")
        return float(response)

    def set_alpha(self, value: float):
        return self._send_command(f"ALPHA={value}")

    def set_offset(self, sensor_index: int, offset: float):
        return self._send_command(f"OFFSET={sensor_index},{offset}")

    def smoothing_on(self):
        return self._send_command("SMOOTHING_ON")

    def smoothing_off(self):
        return self._send_command("SMOOTHING_OFF")

    def log_on(self):
        return self._send_command("LOG_ON")

    def log_off(self):
        return self._send_command("LOG_OFF")

    def debug(self):
        return self._send_command("DEBUG")

    def help(self):
        return self._send_command("HELP")

    def led1_on(self):
        return self._send_command("LED1_ON")

    def led1_off(self):
        return self._send_command("LED1_OFF")

    def led2_on(self):
        return self._send_command("LED2_ON")

    def led2_off(self):
        return self._send_command("LED2_OFF")

    def relay_on(self):
        return self._send_command("RELAY_ON")

    def relay_off(self):
        return self._send_command("RELAY_OFF")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.led1_off()
        self.led2_off()
        self.relay_off()
        self.disconnect()

def test_tc_board(port: str):
    info(f"Testing Arduino TC-Board on port {port}")
    with ArduinoTCBoardSerial(port) as arduino:
        info(arduino.help())
        info(arduino.log_on())
        info(arduino.smoothing_on())
        info(arduino.set_alpha(0.2))
        info(arduino.configure_sensors(list(range(8))))  # S,0,1,...7

        for i in range(8):
            try:
                temp = arduino.read_temperature(i)
                info(f"Temp Sensor[{i}]: {temp:.2f} °C")
            except ValueError as e:
                error(f"Error reading sensor {i}: {e}")

        # LED & Relay test
        arduino.led1_on()
        time.sleep(1)
        arduino.led1_off()
        arduino.led2_on()
        time.sleep(1)
        arduino.led2_off()

        arduino.relay_on()
        time.sleep(2)
        arduino.relay_off()