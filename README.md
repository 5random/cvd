# cvd

## Installation

To install dependencies and this package in editable mode, run:

```bash
pip install -r requirements.txt
pip install -e .
pip install pre-commit black
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
