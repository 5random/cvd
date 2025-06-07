# cvd

## Installation

To install dependencies and this package in editable mode, run:

```bash
pip install -r requirements.txt
pip install -e .
```

The `requirements.txt` file now pins each dependency to a specific version.

## Running tests

Install the test dependencies and run the test suite with `pytest`:

```bash
pip install -r requirements.txt
pytest
```

The tests rely on the `cv2` module from OpenCV and the `nicegui` package. Ensure
both packages are installed and importable.

## Changelog

- Fixed log viewer error caused by removed `last_args` attribute in NiceGUI ScrollArea.
