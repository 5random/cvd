from importlib import import_module

_mod = import_module("legacy_stuff.data_handler.data_handler.interface")
SensorReading = _mod.SensorReading
SensorStatus = _mod.SensorStatus
SensorInterface = _mod.SensorInterface
SensorConfig = _mod.SensorConfig

__all__ = ["SensorReading", "SensorStatus", "SensorInterface", "SensorConfig"]
