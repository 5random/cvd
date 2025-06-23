import importlib


def test_import_src_module():
    """Ensure utilities can be imported from the src package."""
    mod = importlib.import_module("cvd.utils.config_service.loader")
    assert mod is not None
