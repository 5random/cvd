import json
import sys
import types

from src.utils.config_utils.config_service import ConfigurationService
from src.gui.gui_elements import gui_controller_setup_wizard_element as wizard_mod
from src.gui.gui_elements.gui_controller_setup_wizard_element import (
    ControllerSetupWizardComponent,
)


class DummyControllerManager:
    pass


class DummySensorManager:
    pass


def create_service(tmp_path, cfg=None):
    cfg = cfg or {}
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


def test_detects_dummy_camera(monkeypatch, tmp_path):
    class DummyCapture:
        def __init__(self, idx):
            self.idx = idx

        def isOpened(self):
            return True

        def release(self):
            pass

    dummy_cv2 = types.SimpleNamespace(VideoCapture=lambda idx: DummyCapture(idx))
    monkeypatch.setitem(sys.modules, "cv2", dummy_cv2)

    monkeypatch.setattr(
        wizard_mod.ControllerSetupWizardComponent,
        "_update_controller_defaults",
        lambda self: None,
    )

    svc = create_service(tmp_path)
    wizard = ControllerSetupWizardComponent(
        svc, DummyControllerManager(), DummySensorManager()
    )
    webcams = wizard._get_available_webcams()
    assert webcams
    assert "Camera 0 (USB)" in webcams
