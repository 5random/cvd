# Controllers Package

This directory houses the controller framework responsible for processing sensor data and higher level algorithms. `controller_base.py` defines abstract controller stages and common dataclasses while `controller_manager.py` orchestrates execution and dependency management. The `algorithms` subpackage contains built–in controllers such as motion detection and reactor state estimation, and `controller_utils` offers camera helpers and controller-specific data sources.
