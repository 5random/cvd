from importlib import import_module

mod = import_module("legacy_stuff.data_handler.interface.sensor_interface")

SensorStatus = mod.SensorStatus
SensorReading = mod.SensorReading
SensorInterface = mod.SensorInterface
SensorConfig = mod.SensorConfig

__all__ = ["SensorStatus", "SensorReading", "SensorInterface", "SensorConfig"]
