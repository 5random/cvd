import json
import numpy as np
import pytest
from nicegui import ui

from src.utils.config_utils.config_service import ConfigurationService
from src.gui.gui_elements import gui_controller_setup_wizard_element as wizard_mod
from src.gui.gui_elements.gui_controller_setup_wizard_element import (
    ControllerSetupWizardComponent,
)


class DummySensorManager:
    pass


class DummyControllerManager:
    pass


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

    def clear(self):
        return None

    def open(self):
        return None

    def close(self):
        return None


class DummyImage(Dummy):
    def __init__(self) -> None:
        super().__init__()
        self.source = None

    def set_source(self, src) -> None:
        self.source = src


def create_service(tmp_path, cfg=None):
    cfg = cfg or {}
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


@pytest.fixture
def dummy_ui(monkeypatch):
    messages = []

    def dummy_element(*a, **k):
        return Dummy()

    def dummy_image(*a, **k):
        return DummyImage()

    for name in ["dialog", "card", "label", "button"]:
        monkeypatch.setattr(ui, name, dummy_element)
    monkeypatch.setattr(ui, "image", dummy_image)
    monkeypatch.setattr(ui, "notify", lambda msg, **kw: messages.append(msg))
    return messages


def test_test_webcam_notifies(monkeypatch, tmp_path, dummy_ui):
    messages = dummy_ui

    class DummyCap:
        def __init__(self, index):
            self.index = index

        def isOpened(self):
            return True

        def set(self, *a):
            pass

        def read(self):
            frame = np.zeros((1, 1, 3), dtype=np.uint8)
            return True, frame

        def release(self):
            pass

    monkeypatch.setattr(wizard_mod.cv2, "VideoCapture", lambda idx: DummyCap(idx))

    service = create_service(tmp_path)
    monkeypatch.setattr(
        ControllerSetupWizardComponent,
        "_update_controller_defaults",
        lambda self: None,
    )
    wizard = ControllerSetupWizardComponent(service, DummyControllerManager(), DummySensorManager())
    wizard._wizard_data["selected_webcam"] = "cam1"
    wizard._step2_elements["webcam_preview"] = DummyImage()
    wizard._test_webcam()

    assert any("successful" in m.lower() for m in messages)
    assert wizard._step2_elements["webcam_preview"].source is not None
