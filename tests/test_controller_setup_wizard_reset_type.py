import json
import pytest
from nicegui import ui
import os

# mypy: ignore-errors


from src.utils import log_service as ls

for name in ["debug", "info", "warning", "error"]:
    setattr(ls, name, lambda *a, **k: None)

from src.utils.config_service import ConfigurationService
from src.gui.gui_elements.gui_controller_setup_wizard_element import (
    ControllerSetupWizardComponent,
)


class Dummy:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def classes(self, *a, **k):
        return self

    def props(self, *a, **k):
        return self

    def bind_value_to(self, *a, **k):
        return self

    def open(self):
        return None


class DummySensorManager:
    pass


class DummyControllerManager:
    pass


def create_service(tmp_path, cfg=None):
    cfg = cfg or {}
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


@pytest.fixture
def dummy_ui(monkeypatch):
    def element(*a, **k):
        return Dummy()

    for name in ["dialog", "card", "column", "row", "label", "button"]:
        monkeypatch.setattr(ui, name, element)

    yield


def test_show_dialog_resets_type(monkeypatch, tmp_path, dummy_ui):
    svc = create_service(tmp_path)
    monkeypatch.setattr(
        ControllerSetupWizardComponent, "_render_stepper", lambda self: None
    )
    wizard = ControllerSetupWizardComponent(
        svc, DummyControllerManager(), DummySensorManager()
    )

    default_type = wizard._wizard_data["type"]
    other_type = next(t for t in wizard._controller_types if t != default_type)
    wizard._wizard_data["type"] = other_type

    wizard.show_dialog()

    assert wizard._wizard_data["type"] == default_type
