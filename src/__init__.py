"""Main package for the CVD Tracker application.

This package also exposes backwards compatibility shims for legacy modules that
live in the :mod:`legacy_stuff` directory.  Importing ``src.data_handler`` or
``src.legacy_sensors`` will transparently load the old implementations.
"""

from importlib import import_module
import sys

# Re-export legacy packages so old import paths continue to work
legacy_sensors = import_module("legacy_stuff")
data_handler = import_module("legacy_stuff.data_handler")

sys.modules[__name__ + ".data_handler"] = data_handler

__all__ = ["legacy_sensors", "data_handler"]
