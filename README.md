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
make install
pip install pre-commit black
```

The `requirements.txt` file lists the dependencies required by this project.

## Running tests

Install the dependencies and run the test suite with:

```bash
make install
make test
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
