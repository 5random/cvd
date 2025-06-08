# Usage Examples

This page gives a few quick examples of how to use components of the CVD Tracker package.

## Starting the GUI

The application is started through the :class:`~src.utils.container.ApplicationContainer` which wires
up all services and launches the NiceGUI interface.  The configuration directory can be specified on
the command line using ``--config-dir`` or via the ``CVD_CONFIG_DIR`` environment variable.

```python
from pathlib import Path
from src.utils.container import ApplicationContainer

# Load configuration from the ``program/config`` directory
container = ApplicationContainer.create_sync(Path("program/config"))
container.start_gui()
```

To start the application from the command line with a custom configuration
directory run:

```bash
python program/main.py --config-dir program/config
```

You can also set ``CVD_CONFIG_DIR`` instead of passing the argument.

## Working with Mock Sensors

Mock sensor classes allow you to exercise the data pipeline without any hardware connected.

```python
import asyncio
from src.data_handler.sources.mock_sensors import MockRS232Sensor
from src.data_handler.interface.sensor_interface import SensorConfig

config = SensorConfig(sensor_id="mock1", sensor_type="rs232")
sensor = MockRS232Sensor(config)

async def read_once():
    await sensor.initialize()
    reading = await sensor.read()
    print(reading)
    await sensor.shutdown()

asyncio.run(read_once())
```

## Adding a sensor to the configuration

The configuration service accepts a dictionary describing the sensor.  Set the
optional `show_on_dashboard` field to control whether the sensor appears on the
dashboard.

```python
from src.utils.config_utils.config_service import ConfigurationService

service = ConfigurationService(Path("program/config/config.json"), Path("program/config/default.json"))
service.add_sensor_config({
    "sensor_id": "mock1",
    "name": "Example",
    "type": "temperature",
    "source": "mock",
    "interface": "usb",
    "enabled": True,
    "show_on_dashboard": True,
})
```
