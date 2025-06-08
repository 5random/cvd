# Controllers Package

This directory houses the controller framework responsible for processing sensor data and higher level algorithms. `controller_base.py` defines abstract controller stages and common dataclasses while `controller_manager.py` orchestrates execution and dependency management. The `algorithms` subpackage contains built–in controllers such as motion detection and reactor state estimation, and `controller_utils` offers camera helpers and controller-specific data sources.


## Controller Manager

`ControllerManager` is responsible for instantiating controllers, resolving their
dependencies and running them in the correct order. Controllers are registered
either programmatically using `register_controller()` or by loading
configuration dictionaries via `add_controller_from_config()`.

The typical lifecycle of a controller is:

1. **Creation** – a `ControllerStage` subclass is constructed with a
   `ControllerConfig` instance.
2. **Start** – `ControllerManager.start_all_controllers()` calls each
   controller's `start()` method which in turn invokes `initialize()`.
3. **Processing** – for every batch of sensor readings
   `ControllerManager.process_data()` prepares a `ControllerInput` and calls the
   controller's `process()` method.  Results are stored so that dependent
   controllers can use them.
4. **Stop** – when shutting down `stop_all_controllers()` invokes the
   controller's `stop()` which triggers `cleanup()` and transitions the status
   to `STOPPED`.

`ControllerManager.add_dependency()` establishes a directed dependency between
two controllers. During processing the output of the source controller is passed
to the target according to an optional `data_mapping` dictionary.

### Controller Configuration

`ControllerConfig` is a dataclass describing how a controller should behave.
Important fields include:

- `controller_id` – unique identifier used when registering the controller.
- `controller_type` – string defining the implementation type
  (e.g. `"motion_detection"`).
- `enabled` – whether the controller participates in processing.
- `parameters` – dictionary of arbitrary configuration values consumed by the
  controller implementation.
- `input_sensors` – optional list of sensor IDs to filter incoming data.
- `input_controllers` – optional list restricting which controller outputs are
  provided as dependencies.
- `output_name` – optional key under which the controller stores its primary
  result.

Dependencies are added after controllers are registered:

```python
manager.add_dependency("camera_capture", "motion_detection",
                       data_mapping={"frame": "image"})
```

## Implementing a Custom Controller

To create a new controller subclass `ControllerStage` and implement the
asynchronous `process()` method. After instantiation register the controller
with a manager:

```python
from src.controllers.controller_base import ControllerStage, ControllerConfig,
    ControllerInput, ControllerResult


class ExampleController(ControllerStage):
    async def process(self, input_data: ControllerInput) -> ControllerResult:
        # Simple example that always returns 42
        return ControllerResult.success_result({"value": 42})


cfg = ControllerConfig(controller_id="example", controller_type="custom")
ctrl = ExampleController("example", cfg)
manager = create_test_controller_manager()
manager.register_controller(ctrl)
```

The new controller will now participate in the normal lifecycle managed by
`ControllerManager` alongside any built‑in controllers.

## Registering Controller Types

`controller_manager` exposes a small registry so additional controllers can be
hooked into the system. Use `register_controller_type` to associate a type name
with your controller class:

```python
from src.controllers.controller_manager import register_controller_type
from mypackage.mycontroller import MyController

register_controller_type("my_controller", MyController)
```

Registered types can then be referenced from configuration files or when calling
`create_controller` on a `ControllerManager` instance.

## Logging Guidelines

Controllers log via `src.utils.log_utils.log_service`. Include the
`controller_id` and any relevant metadata (e.g. source sensor or algorithm)
with every message.

- Use `info` for standard lifecycle events.
- Use `warning` for recoverable problems.
- Use `error` for failures or unexpected exceptions.

Example:

```python
info("Controller started", controller_id=self.controller_id, algorithm="MOG2")
warning(
    "Camera not opened, reinitializing",
    controller_id=self.controller_id,
    device_index=self.device_index,
)
```

Providing metadata keeps logs machine friendly for monitoring tools.
