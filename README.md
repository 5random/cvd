# cvd

## Project Overview

This project implements the **CVD Tracker** application used to collect
data from various sensors, process it with controllers and display results
through a NiceGUI based interface.  A short description of the architecture
and main modules can be found in [docs/architecture.md](docs/architecture.md).
Example snippets demonstrating typical usage are available in
[docs/examples.md](docs/examples.md).

## Installation

To install dependencies and this package in editable mode, run:

```bash
pip install -e .
pip install pre-commit black
```

All dependencies are defined in `pyproject.toml`. Both `setup.py` and
`requirements.txt` read from this file so there is a single authoritative list.


The installed package includes a `config/` directory containing the default
configuration file as well as sample data under `data/`.  When installing with
`pip install .`, these files are placed inside the package directory so the
application can be started without additional setup.

## Usage

Launch the GUI application specifying the configuration directory:

```bash
python program/main.py --config-dir program/config
```

You may also set the ``CVD_CONFIG_DIR`` environment variable instead of passing
``--config-dir``.

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


## Running tests

Before running the tests you must install this package and its dependencies.
Attempting to execute `pytest` without installation will result in import
errors.  Install everything with:

```bash

pip install -e .
make test
make install    # or: pip install -e .
```

After installation run the test suite with:

```bash
pytest          # or: make test

```

The tests rely on the `cv2` module from OpenCV and the `nicegui` package. Ensure
both packages are installed and importable.

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
