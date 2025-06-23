import logging
import json
import pytest
from cvd.controllers.controller_manager import ControllerManager
from cvd.controllers.webcam import MotionDetectionController
from cvd.controllers.algorithms.reactor_state import ReactorStateController
from cvd.controllers.controller_registry import register_controller_type
from cvd.utils.config_service import ConfigurationError


def test_create_known_controller_types():
    manager = ControllerManager()
    register_controller_type("reactor_state", ReactorStateController)
    md = manager.create_controller({"controller_id": "md1", "type": "motion_detection"})
    rs = manager.create_controller({"controller_id": "rs1", "type": "reactor_state"})
    assert isinstance(md, MotionDetectionController)
    assert isinstance(rs, ReactorStateController)


def test_create_controller_missing_required_fields_raises(caplog):
    manager = ControllerManager()
    caplog.set_level(logging.ERROR, logger="cvd_tracker.error")
    with pytest.raises(ConfigurationError):
        manager.create_controller({"controller_id": "missing_type"})


def test_create_controller_unknown_type_returns_none(caplog):
    manager = ControllerManager()
    caplog.set_level(logging.ERROR, logger="cvd_tracker.error")
    result = manager.create_controller({"controller_id": "c1", "type": "unknown"})
    assert result is None


def test_save_configuration_creates_directory(tmp_path):
    manager = ControllerManager()
    cfg_path = tmp_path / "nested" / "controllers.json"
    result = manager.save_configuration(cfg_path)
    assert result is True
    assert cfg_path.exists()


def test_save_configuration_includes_controller_type(tmp_path):
    manager = ControllerManager()
    manager.add_controller_from_config(
        {"controller_id": "cam1", "type": "camera_capture"}
    )
    cfg_path = tmp_path / "controllers.json"
    result = manager.save_configuration(cfg_path)
    assert result is True
    data = json.loads(cfg_path.read_text())
    assert data["controllers"]["cam1"]["controller_type"] == "camera_capture"
