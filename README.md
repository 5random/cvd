# cvd

## Project Overview

This project implements the **CVD Tracker** application used to collect
data from various sensors, process it with controllers and display results
through a NiceGUI based interface.  A short description of the architecture
and main modules can be found in [docs/architecture.md](docs/architecture.md).
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

All dependencies are defined in `pyproject.toml`. Both `setup.py` and
`requirements.txt` read from this file so there is a single authoritative list.
Run the helper script whenever you change the dependency list to keep
`requirements.txt` up to date:

```bash
python scripts/update_requirements.py
```


The installed package includes a `config/` directory containing the default
configuration file. Directories used for runtime data such as
`data/experiment_data`, `data/experiments` and `data/processed` are not
tracked in version control. They will be created automatically the first time
you run the application or you can create them manually if needed.

The repository also ships with example configurations located in
`program/config`.  These files illustrate typical setups and can serve as a
starting point for your own configuration.  The top-level `config/` directory is
only used by the test suite and should not be modified for normal operation.

## Usage

Launch the GUI application specifying the configuration directory:

```bash
python program/main.py --config-dir program/config
```

To run the application with your own configuration directory simply point
`--config-dir` to the folder containing your files:

```bash
python program/main.py --config-dir path/to/my_config
```

You may also set the ``CVD_CONFIG_DIR`` environment variable instead of passing
``--config-dir``.

When creating a custom ``SimpleGUIApplication`` make sure to call
``set_config_service`` after instantiating the
``ConfigurationService``. This allows helper functions such as
``create_cvd_controller_manager`` and ``get_email_alert_service`` to read from
the same configuration instance.

Use the fullscreen button in the header to toggle between windowed and fullscreen mode.

### Camera stream endpoints

Each camera stream component exposes its frames via an HTTP endpoint.  The
default stream remains available under ``/video_feed``.  Individual cameras can
be accessed at ``/video_feed/{cid}`` where ``cid`` is the controller ID used on
the dashboard.

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
``program/main.py`` which simply sets this environment variable for you.

### Webcam UVC settings

Webcam properties under ``uvc_settings`` follow OpenCV naming. The property
``"backlight_compensation"`` can also be provided as ``"backlight_comp"`` and
will be interpreted the same way.

### Video capture backend

You may explicitly select the OpenCV backend used for capturing frames by
providing ``"capture_backend"`` in a webcam or controller configuration. Common
values include ``cv2.CAP_DSHOW`` and ``cv2.CAP_MSMF`` on Windows. If omitted,
OpenCV will choose the default backend for the platform.

### External camera capture

The motion detection controller can rely on another controller for camera frames.
Set ``input_controllers`` to the ID of a ``camera_capture`` controller to disable
its internal capture loop and use the external source instead.


## Running tests

Before running the tests you must install this package and its dependencies.
Attempting to execute `pytest` without installation will result in import
errors.

Install the dependencies and run the tests in a single sequence. You can
either install the package in editable mode or use the requirements files:

```bash
pip install -e .
pytest          # or: make test

# or install from the requirements files
pip install -r requirements.txt
pytest

# for development utilities (linters, pre-commit hook)
pip install -r dev-requirements.txt

```

The tests rely on several runtime packages such as `opencv-python` (for the
`cv2` module) and `nicegui`. Both are included in `requirements.txt`, so running
``pip install -e .`` or ``pip install -r requirements.txt`` before invoking
`pytest` will install them automatically.

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

- Fixed log viewer error caused by removed `last_args` attribute in NiceGUI ScrollArea.

## License

This project is released under the [MIT License](LICENSE).
