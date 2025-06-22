from importlib import import_module
import sys

_mod = import_module("legacy_stuff.data_handler")
__all__ = list(getattr(_mod, "__all__", []))
__path__ = getattr(_mod, "__path__", [])
for _k, _v in _mod.__dict__.items():
    globals()[_k] = _v
sys.modules[__name__] = _mod
