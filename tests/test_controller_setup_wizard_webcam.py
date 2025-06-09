import json
import numpy as np
import pytest
import types
from nicegui import ui
import sys, os
sys.path.insert(0, os.path.abspath("program"))

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


class DummyInteractiveImage(Dummy):
    def __init__(self) -> None:
        super().__init__()
        self.callback = None

    def on_mouse(self, cb):
        self.callback = cb
        return self

    def add_layer(self):
        return types.SimpleNamespace(content="")


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

    def dummy_interactive(*a, **k):
        img = DummyInteractiveImage()
        dummy_interactive.last = img
        return img

    monkeypatch.setattr(ui, "interactive_image", dummy_interactive)
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
    wizard = ControllerSetupWizardComponent(
        service, DummyControllerManager(), DummySensorManager()
    )
    wizard._wizard_data["selected_webcam"] = "cam1"
    wizard._step2_elements["webcam_preview"] = DummyImage()
    wizard._test_webcam()

    assert any("successful" in m.lower() for m in messages)
    assert wizard._step2_elements["webcam_preview"].source is not None


def test_on_webcam_change_updates_index(monkeypatch, tmp_path):
    service = create_service(tmp_path)
    monkeypatch.setattr(
        ControllerSetupWizardComponent,
        "_update_controller_defaults",
        lambda self: None,
    )
    wizard = ControllerSetupWizardComponent(
        service, DummyControllerManager(), DummySensorManager()
    )

    monkeypatch.setattr(wizard, "_render_webcam_selection", lambda: None)

    wizard._on_webcam_change(types.SimpleNamespace(value="Camera 2 (USB)"))

    assert wizard._wizard_data["webcam_config"]["device_index"] == 2


def test_test_webcam_uses_device_index(monkeypatch, tmp_path, dummy_ui):
    messages = dummy_ui

    used_index = {}

    class DummyCap:
        def __init__(self, index):
            used_index["value"] = index

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
    wizard = ControllerSetupWizardComponent(
        service, DummyControllerManager(), DummySensorManager()
    )
    wizard._wizard_data["webcam_config"]["device_index"] = 3
    wizard._wizard_data["selected_webcam"] = "cam1"
    wizard._step2_elements["webcam_preview"] = DummyImage()
    wizard._test_webcam()

    assert used_index["value"] == 3



def test_roi_updates_on_draw(monkeypatch, tmp_path, dummy_ui):
    messages = dummy_ui


def test_on_webcam_change_triggers_preview(monkeypatch, tmp_path):

    service = create_service(tmp_path)
    monkeypatch.setattr(
        ControllerSetupWizardComponent,
        "_update_controller_defaults",
        lambda self: None,
    )
    wizard = ControllerSetupWizardComponent(
        service, DummyControllerManager(), DummySensorManager()
    )


    monkeypatch.setattr(wizard, "_refresh_step3", lambda: None)

    wizard._wizard_data["parameters"] = {"roi_x": 0, "roi_y": 0, "roi_width": 0, "roi_height": 0}

    wizard._show_roi_selector()

    img = ui.interactive_image.last
    cb = img.callback

    cb(types.SimpleNamespace(type="mousedown", image_x=10, image_y=20))
    cb(types.SimpleNamespace(type="mousemove", image_x=40, image_y=60))

    assert wizard._wizard_data["parameters"]["roi_x"] == 10
    assert wizard._wizard_data["parameters"]["roi_y"] == 20
    assert wizard._wizard_data["parameters"]["roi_width"] == 30
    assert wizard._wizard_data["parameters"]["roi_height"] == 40

    # stub render method to create preview element
    monkeypatch.setattr(
        wizard,
        "_render_webcam_selection",
        lambda: wizard._step2_elements.update({"webcam_preview": DummyImage()}),
    )

    called = {}
    monkeypatch.setattr(wizard, "_test_webcam", lambda: called.setdefault("ok", True))

    wizard._on_webcam_change(types.SimpleNamespace(value="Camera 1 (USB)"))

    assert called.get("ok")

