# Test Setup

The test suite relies on the runtime dependencies listed in `requirements.txt` as well as a few additional packages used only during development. Install the dependencies before running any tests:

```bash
pip install -r requirements.txt -r dev-requirements.txt
```

This will install the following third-party packages:

- **Pillow** – image utilities for the GUI and motion detection tests.
- **jsonschema** – schema validation for configuration files.
- **nicegui** – GUI framework used in end-to-end tests.
- **numpy** – numeric operations and array manipulations.
- **opencv-python** – camera handling and image processing.
- **plotly** – plotting library for visual outputs.
- **psutil** – system metrics shown on the dashboard.
- **pyserial** – serial communication with hardware sensors.
- **setuptools** – required for packaging and for the editable install used in CI.
- **types-jsonschema**, **types-setuptools** – type hints for the above packages.
- **watchdog** – file watching used in a few test helpers.
- **pre-commit**, **black**, **mypy** – development tools run as part of `pre-commit`.
- **pytest**, **pytest-asyncio** – the test framework and asyncio support.

After installation, run the tests with:

```bash
pytest
```


