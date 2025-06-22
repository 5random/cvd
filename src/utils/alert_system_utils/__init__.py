from importlib import import_module
import sys

_mod = import_module("src.utils.email_alert_service")
_alias = __name__ + ".email_alert_service"
__all__ = list(getattr(_mod, "__all__", []))
for _k, _v in _mod.__dict__.items():
    globals()[_k] = _v
sys.modules[_alias] = _mod
