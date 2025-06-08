# Controllers Package

This directory houses the controller framework responsible for processing sensor data and higher level algorithms. `controller_base.py` defines abstract controller stages and common dataclasses while `controller_manager.py` orchestrates execution and dependency management. The `algorithms` subpackage contains built–in controllers such as motion detection and reactor state estimation, and `controller_utils` offers camera helpers and controller-specific data sources.

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
