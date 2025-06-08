# Controllers Package

This directory houses the controller framework responsible for processing sensor data and higher level algorithms. `controller_base.py` defines abstract controller stages and common dataclasses while `controller_manager.py` orchestrates execution and dependency management. The `algorithms` subpackage contains built–in controllers such as motion detection and reactor state estimation, and `controller_utils` offers camera helpers and controller-specific data sources.

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
