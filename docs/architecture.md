# Architecture Overview

This document provides a high level summary of the main components of the CVD Tracker application and how they interact.  The project is organised as a Python package located under the `program` directory.

## Sensors

Sensor implementations live in `program/src/data_handler/sources` and adhere to the `SensorInterface`. Sensors are created and managed by `SensorManager` which loads configuration from the `ConfigurationService`. `SensorManager` spawns asynchronous polling tasks and forwards readings through a processing pipeline. The latest sensor readings are cached so that other components such as controllers or the GUI can access them.

## Controllers

Controllers implement processing algorithms that operate on sensor data. They are managed by `ControllerManager` under `program/src/controllers`. Controllers can depend on the outputs of other controllers. The manager handles creation from configuration, dependency resolution and orchestrated execution when new sensor data arrives.

## GUI

The user interface is implemented with NiceGUI in `program/src/gui`. The `WebApplication` class wires together different tab components for sensors, controllers, experiments and log viewing. It also starts background tasks that periodically process data via `ControllerManager`. Routes and layouts are registered when starting the GUI and the application can be run headless for tests.

## Data Utilities

Data from sensors and controllers is persisted using utility classes under `program/src/utils/data_utils`. `DataSaver` handles writing CSV files and triggers compression/rotation through `CompressionService`. Additional helpers manage data directories and provide access to past data.

## Service Container

The central entry point is `ApplicationContainer` defined in `program/src/utils/container.py`. It instantiates and connects the services above: configuration, sensors, data utilities, web application and alerting. Background tasks such as sensor polling run inside this container. `ApplicationContainer` exposes `startup`, `shutdown` and `start_gui` methods used by the main script.

The executable in `program/main.py` creates the container via `ApplicationContainer.create_sync()` and launches the NiceGUI application. When the program exits, registered cleanup handlers invoke `container.shutdown_sync()` to stop background services gracefully.

## Component Interaction

1. `ApplicationContainer` reads configuration and builds `SensorManager`, `DataSaver` and `WebApplication`.
2. `WebApplication` uses `SensorManager` and `ControllerManager` to populate dashboards and handle user actions.
3. `SensorManager` gathers data from sensor drivers and passes it to a processing pipeline before saving via `DataSaver`.
4. `ControllerManager` processes sensor readings and controller outputs which can then be shown in the GUI or stored.

For more details see the source files referenced above such as [`program/src/utils/container.py`](../program/src/utils/container.py) and [`program/main.py`](../program/main.py).

## UML Diagram

The full class diagram below is generated automatically from the source
tree using `scripts/generate_uml.py`. It lists every class defined under
`program/src` along with detected attributes and methods. Comments
preceding classes, variables and functions contain short descriptions
extracted from their docstrings or type hints and highlight inheritance
relationships. Inline comments next to variable definitions are also
captured so the diagram explains what each field represents. Private
attributes and methods are omitted to keep the diagram concise.

Run `python scripts/generate_uml.py > docs/full_class_diagram.mmd` to
regenerate the diagram. The `full_class_diagram.mmd` file is already
included in the repository and can be updated whenever the source code
changes.

```{literalinclude} full_class_diagram.mmd
:language: mermaid
```

