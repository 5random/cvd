from importlib import import_module
import sys

_mod = import_module('src.gui.gui_native.application')
__all__: list[str] = list(getattr(_mod, "__all__", []))
__path__ = getattr(_mod, '__path__', [])
for k, v in _mod.__dict__.items():
    globals()[k] = v
sys.modules[__name__] = _mod
