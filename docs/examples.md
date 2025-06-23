# Usage Examples

This page gives a few quick examples of how to use components of the CVD Tracker package.

## Starting the GUI

The application is started through the `ApplicationContainer` which wires
up all services and launches the NiceGUI interface. The configuration directory
can be specified on the command line using ``--config-dir`` or via the
``CVD_CONFIG_DIR`` environment variable.

```python
from pathlib import Path
from cvd.utils.container import ApplicationContainer

# Load configuration from the ``src/cvd/config`` directory
container = ApplicationContainer.create_sync(Path("src/cvd/config"))
container.start_gui()
```

To start the application from the command line with a custom configuration
directory run:

```bash
python main.py --config-dir src/cvd/config
```

You can also set ``CVD_CONFIG_DIR`` instead of passing the argument.

## Working with Mock Sensors

Mock sensor classes allow you to exercise the data pipeline without any hardware connected.

```python
import asyncio
from cvd.data_handler.sources.mock_sensors import MockRS232Sensor
from cvd.data_handler.interface.sensor_interface import SensorConfig

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
from cvd.utils.config_service import ConfigurationService

service = ConfigurationService(Path("src/cvd/config/config.json"), Path("src/cvd/config/default_config.json"))
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


## Registering custom sensors via entry points

Third-party packages can contribute new sensor implementations without
modifying the main repository. Expose a factory under the
``cvd.sensors`` entry point group in your ``pyproject.toml``:

```toml
[project.entry-points."cvd.sensors"]
my_sensor = "your_package.sensors:MySensor"
```

When ``sensor_source_manager`` is imported, all entry points in this group
are loaded and added to ``SENSOR_REGISTRY`` so the sensor can be used in
the configuration.

## Sensor Setup Wizard

The NiceGUI interface includes a multi-step wizard for defining sensors.
On step 2 you can click **Test Connection** to verify the settings
before creating the sensor. The wizard temporarily creates the device,
reads once and then cleans up, displaying the result as a notification.

## Controller Configuration Options

Controller settings use predefined option lists for certain values. For example
the motion detection controller only accepts ``"MOG2"`` or ``"KNN"`` as the
background subtraction algorithm. The `ConfigurationService` exposes
helpers such as ``get_controller_type_options()`` and ``get_webcam_ids()`` which
GUI components use to populate dropdown menus.


Motion detection also supports a multi-frame decision mode. Set
``multi_frame_enabled`` to ``true`` and choose a ``multi_frame_method`` of
``"threshold"`` or ``"probability"``. The ``threshold`` method counts detections
over ``multi_frame_window`` frames while ``probability`` computes an exponential
moving average of detection confidence using ``multi_frame_decay``. Motion is
reported only when the resulting value exceeds ``multi_frame_threshold``.

The motion detection controller also supports defining a region of interest
within the camera frame. Provide ``roi_x`` and ``roi_y`` for the top-left corner
along with ``roi_width`` and ``roi_height`` to restrict detection to that area.

``motion_threshold_percentage`` defines the minimum percentage of the frame that
must contain motion to trigger a detection. Specify this value in percent, so a
threshold of ``1`` requires motion in 1% of the frame.

When cropping is active, the returned ``motion_bbox`` and ``motion_center``
values are offset by ``roi_x`` and ``roi_y`` so they refer to coordinates in the
original frame. Overlay code drawing on the cropped frame should subtract these
offsets to align correctly.

