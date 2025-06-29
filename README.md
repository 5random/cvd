# cvd

## Project Overview

This project implements the **CVD Tracker** application used to collect
data from various sensors, process it with controllers and display results
through a NiceGUI based interface.  A short description of the architecture
and main modules can be found in [docs/architecture.md](docs/architecture.md).
For a quick overview of how controllers feed into each other see [docs/architecture.md#controller-dependencies](docs/architecture.md#controller-dependencies).
Example snippets demonstrating typical usage are available in
[docs/examples.md](docs/examples.md).
An overview of the configuration and logging utilities lives in
[docs/utils_services.md](docs/utils_services.md).

## Installation

This project requires **Python 3.11** or newer. Ensure a compatible
interpreter is available before installing any dependencies.

To install dependencies and this package in editable mode, run:

```bash
pip install -e .
pip install pre-commit black
```

You may also install the pinned dependencies from the generated
`requirements.txt` file. This is useful for running the test suite on a
fresh environment:

```bash
pip install -r requirements.txt
```

Development utilities such as linters and the pre-commit hook are collected in
`dev-requirements.txt`:

```bash
pip install -r dev-requirements.txt
```

This installs all Python dependencies including `psutil`, which the dashboard
uses to display CPU and memory usage.

All runtime dependencies are declared under ``[project.dependencies]`` in
``pyproject.toml``.  The ``setup.py`` and ``requirements.txt`` files both read
from this section so there is a single authoritative list.  Whenever you edit
``pyproject.toml`` to add or remove a package you must regenerate
``requirements.txt``.  Use the helper script to update the file:

```bash
python scripts/update_requirements.py
```

This extracts the dependencies from ``pyproject.toml`` and writes them sorted to
``requirements.txt``.  You can also run the convenience target below which wraps
the same command:

```bash
make update-requirements
```


The installed package includes a `config/` directory containing the default
configuration file. Directories used for runtime data such as
`data/experiment_data`, `data/experiments` and `data/processed` are not
tracked in version control. They will be created automatically the first time
you run the application or you can create them manually if needed.


The repository also ships with example configurations located in
`src/cvd/config`.  These files illustrate typical setups and can serve as a
starting point for your own configuration.  The top-level `config/` directory is
only used by the test suite and should not be modified for normal operation.

## Configuration

Configuration values are loaded from `config.json` and merged with
`default_config.json`. Set ``CVD_CONFIG_DIR`` or pass ``--config-dir`` to point to
your configuration folder.

The following option can be used to run the application without physical sensor
hardware:

* ``disable_hardware_sensors`` – when ``true`` hardware based sensors such as
  ``ArduinoTCSensor`` and ``RS232Sensor`` will not be registered.

## Usage

Launch the GUI application specifying the configuration directory:

```bash
python main.py --config-dir src/cvd/config
```

To run the application with your own configuration directory simply point
`--config-dir` to the folder containing your files:

```bash
python main.py --config-dir path/to/my_config
```

You may also set the ``CVD_CONFIG_DIR`` environment variable instead of passing
``--config-dir``.

When creating a custom ``SimpleGUIApplication`` make sure to call
``set_config_service`` after instantiating the
``ConfigurationService``. This allows helper functions such as
``create_cvd_controller_manager`` to read from the same configuration
instance while still letting you pass the ``EmailAlertService`` explicitly
where needed.

Use the fullscreen button in the header to toggle between windowed and fullscreen mode.

### Simplified GUI

For a minimal webcam demo you can run the alternative GUI located in
``src/cvd/gui/alt_application.py``. It loads the example configuration from
``src/cvd/config/simple_config.json``:

```bash
python src/cvd/gui/alt_application.py
```

### Camera stream endpoints

Each camera stream component exposes its frames via an HTTP endpoint.  The
default stream remains available under ``/video_feed``.  Individual cameras can
be accessed at ``/video_feed/{cid}`` where ``cid`` is the controller ID used on
the dashboard.

Toggling the camera view in the dashboard only enables or disables streaming of
the MJPEG feed. The capture process continues in the background so motion
detection remains active even when no video is displayed.

### Dashboard visibility

Sensors and controllers defined in the configuration will only appear on the
dashboard when their configuration contains ``"show_on_dashboard": true``.
Add this flag under each sensor or controller entry to control what is visible
in the GUI.

### Controller concurrency

The controller manager controls how many controllers may execute in parallel.
Set the ``CONTROLLER_MANAGER_CONCURRENCY_LIMIT`` environment variable to adjust
this number. If unset, it defaults to ``10``. You can also provide the same
value on startup using the ``--controller-concurrency-limit`` option of

``main.py`` which simply sets this environment variable for you.

### Webcam UVC settings

Webcam properties under ``uvc_settings`` follow OpenCV naming. Use
``"backlight_compensation"`` for adjusting backlight compensation.

### Video capture backend

You may explicitly select the OpenCV backend used for capturing frames by
providing ``"capture_backend"`` in a webcam or controller configuration. Common
values include ``cv2.CAP_DSHOW`` and ``cv2.CAP_MSMF`` on Windows. If omitted,
OpenCV will choose the default backend for the platform. When a backend fails
to produce frames you can specify additional candidates using
``"capture_backend_fallbacks"``. If no fallbacks are provided the library will
attempt ``cv2.CAP_DSHOW`` on Windows or ``cv2.CAP_V4L2`` on Linux.

### Enumerating supported camera modes

``probe_camera_modes()`` tests a set of common resolution/FPS pairs to
discover what the connected camera supports.  The function now reuses a single
``cv2.VideoCapture`` instance while cycling through the options instead of
reopening the device for every combination.  This speeds up probing on systems
where camera initialization is slow.

### External camera capture

The motion detection controller can rely on another controller for camera frames.

Set ``input_controllers`` to the ID of a ``camera_capture`` controller to disable
its internal capture loop and use the external source instead.
Webcam related controllers, including ``camera_capture`` and ``motion_detection``,
live in the ``src/cvd/controllers/webcam`` subpackage.

### Disable sensors

The global configuration accepts a ``"disable_sensors"`` flag. When set to
``true`` no sensors will be initialised at startup. This is handy for camera
only setups or when running tests without real hardware.


## Running tests

Install **all** runtime and development dependencies before executing the test
suite. The easiest method is to install both requirement files together:

```bash
pip install -r requirements.txt -r dev-requirements.txt
```

These packages include critical libraries such as `opencv-python` (for the
`cv2` module), `nicegui` and `jsonschema` which are required by many tests.
A more detailed list is available in
[docs/test_setup.md](docs/test_setup.md).

After installation run the tests:

```bash
pytest          # or: make test
```


## Code style

This project uses `black` for formatting and the `pre-commit` framework to
enforce style checks. Install the tools and set up the git hook with:

```bash
pip install pre-commit black
pre-commit install
```

Run all style checks manually with:

```bash
pre-commit run --all-files
```

## Changelog

- See [CHANGELOG](CHANGELOG.md) for a list of recent updates.

## License

This project is released under the [MIT License](LICENSE).
