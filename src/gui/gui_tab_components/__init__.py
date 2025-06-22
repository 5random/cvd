from importlib import import_module
import sys

_mod = import_module('src.gui.gui_native.gui_tab_components')
__path__ = list(_mod.__path__)
__all__: list[str] = list(getattr(_mod, "__all__", []))

for k, v in _mod.__dict__.items():
    globals()[k] = v

sys.modules[__name__] = _mod
