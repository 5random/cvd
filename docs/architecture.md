# Architecture Overview

This document provides a high level summary of the main components of the CVD Tracker application and how they interact.  The project is organised as a Python package located under the `src` directory.

## Sensors

Sensor implementations live in `src/cvd/data_handler/sources` and adhere to the `SensorInterface`. Sensors are created and managed by `SensorManager` which loads configuration from the `ConfigurationService`. `SensorManager` spawns asynchronous polling tasks and forwards readings through a processing pipeline. The latest sensor readings are cached so that other components such as controllers or the GUI can access them.

## Controllers

Controllers implement processing algorithms that operate on sensor data. They are managed by `ControllerManager` under `src/cvd/controllers`. Controllers can depend on the outputs of other controllers. The manager handles creation from configuration, dependency resolution and orchestrated execution when new sensor data arrives.
Webcam-oriented controllers are located in the `src/cvd/controllers/webcam` subpackage.

## Controller Dependencies

Controllers may form pipelines by consuming the outputs of other controllers. The
default setup connects the `camera_capture` controller to `motion_detection` so
that video frames feed directly into the motion algorithm. Additional
dependencies can be defined in configuration, for example feeding
`motion_detection` results into a `reactor_state` controller. The manager resolves
these links at startup so each controller receives the appropriate inputs.

## GUI

The user interface is implemented with NiceGUI in `src/cvd/gui`. The `WebApplication` class wires together different tab components for sensors, controllers, experiments and log viewing. It also starts background tasks that periodically process data via `ControllerManager`. Routes and layouts are registered when starting the GUI and the application can be run headless for tests.

## Data Utilities

Data from sensors and controllers is persisted using utility classes under `src/cvd/utils/data_utils`. `DataSaver` handles writing CSV files and triggers compression/rotation through `CompressionService`. Additional helpers manage data directories and provide access to past data.

## Service Container

The central entry point is `ApplicationContainer` defined in `src/cvd/utils/container.py`. It instantiates and connects the services above: configuration, sensors, data utilities, web application and alerting. Background tasks such as sensor polling run inside this container. `ApplicationContainer` exposes `startup`, `shutdown` and `start_gui` methods used by the main script.

The executable in `main.py` creates the container via `ApplicationContainer.create_sync()` and launches the NiceGUI application. When the program exits, registered cleanup handlers invoke `container.shutdown_sync()` to stop background services gracefully.

## Component Interaction

1. `ApplicationContainer` reads configuration and builds `SensorManager`, `DataSaver` and `WebApplication`.
2. `WebApplication` uses `SensorManager` and `ControllerManager` to populate dashboards and handle user actions.
3. `SensorManager` gathers data from sensor drivers and passes it to a processing pipeline before saving via `DataSaver`.
4. `ControllerManager` processes sensor readings and controller outputs which can then be shown in the GUI or stored.

For more details see the source files referenced above such as [`src/cvd/utils/container.py`](../src/cvd/utils/container.py) and [`main.py`](../main.py).

## UML Diagram

The full class diagram below is generated automatically from the source
tree using `scripts/generate_uml.py`. It lists every class defined under
`src` along with detected attributes and methods. Comments
preceding classes, variables and functions contain short descriptions
extracted from their docstrings or type hints and highlight inheritance
relationships. Inline comments next to variable definitions are also
captured so the diagram explains what each field represents. Private
attributes and methods are omitted to keep the diagram concise.

Run `python scripts/generate_uml.py > docs/full_class_diagram.mmd` to
regenerate the diagram. The `full_class_diagram.mmd` file is already
included in the repository and can be updated whenever the source code
changes.

The full diagram is available in
[`full_class_diagram.mmd`](full_class_diagram.mmd).


