import importlib
import sys


def _clear(mod_name):
    sys.modules.pop(mod_name, None)


def test_src_then_program_same_object():
    _clear("src.utils.config_service.loader")
    _clear("program.src.utils.config_service.loader")
    mod1 = importlib.import_module("src.utils.config_service.loader")
    mod2 = importlib.import_module("program.src.utils.config_service.loader")
    assert mod1 is mod2
    assert (
        sys.modules["src.utils.config_service.loader"]
        is sys.modules["program.src.utils.config_service.loader"]
    )


def test_program_then_src_same_object():
    _clear("src.utils.config_service.loader")
    _clear("program.src.utils.config_service.loader")
    mod1 = importlib.import_module("program.src.utils.config_service.loader")
    mod2 = importlib.import_module("src.utils.config_service.loader")
    assert mod1 is mod2
    assert (
        sys.modules["src.utils.config_service.loader"]
        is sys.modules["program.src.utils.config_service.loader"]
    )
