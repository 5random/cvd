# cvd

## Installation

To install dependencies and this package in editable mode, run:

```bash
pip install -r requirements.txt
pip install -e .
```

The `requirements.txt` file lists the dependencies required by this project.

## Running tests

Install the dependencies, install this package in editable mode, and run the test suite with `pytest`:

```bash
pip install -r requirements.txt
pip install -e .
pytest
```

The tests rely on the `cv2` module from OpenCV and the `nicegui` package. Ensure
both packages are installed and importable.

## Changelog

- Fixed log viewer error caused by removed `last_args` attribute in NiceGUI ScrollArea.
