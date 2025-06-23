from src.utils.container import ApplicationContainer
from src import gui
from src.gui.alt_gui_elements.alert_element_new import EmailAlertStatusDisplay

class DummyWebApp:
    def __init__(self, *a, **k):
        from types import SimpleNamespace
        
        self.component_registry = SimpleNamespace(cleanup_all=lambda: None)

    async def startup(self):
        pass

    async def shutdown(self):
        pass

    def register_components(self):
        pass


def test_data_saver_flush_interval_from_config(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.gui.alt_application.SimpleGUIApplication", DummyWebApp
    )
    config_dir = tmp_path
    cfg = {
        "data_storage": {
            "storage_paths": {"base": str(tmp_path / "data")},
            "flush_interval": 3,
        }
    }
    (config_dir / "config.json").write_text(__import__("json").dumps(cfg))
    (config_dir / "default_config.json").write_text("{}")

    monkeypatch.setattr(gui, "EmailAlertStatusDisplay", EmailAlertStatusDisplay)
    container = ApplicationContainer.create(config_dir)
    try:
        assert container.data_saver.flush_interval == 3
    finally:
        try:
            container.shutdown_sync()
        except Exception:
            pass


def test_data_saver_flush_interval_defaults_to_one(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.gui.alt_application.SimpleGUIApplication", DummyWebApp
    )
    config_dir = tmp_path
    cfg = {
        "data_storage": {
            "storage_paths": {"base": str(tmp_path / "data")},
            "flush_interval": 0,
        }
    }
    (config_dir / "config.json").write_text(__import__("json").dumps(cfg))
    (config_dir / "default_config.json").write_text("{}")

    monkeypatch.setattr(gui, "EmailAlertStatusDisplay", EmailAlertStatusDisplay)
    container = ApplicationContainer.create(config_dir)
    try:
        assert container.data_saver.flush_interval == 1
    finally:
        try:
            container.shutdown_sync()
        except Exception:
            pass
