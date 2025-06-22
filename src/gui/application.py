from importlib import import_module
import sys

_mod = import_module("legacy_stuff.gui_native.application")
__all__ = list(getattr(_mod, "__all__", []))
for _k, _v in _mod.__dict__.items():
    globals()[_k] = _v
sys.modules[__name__] = _mod
