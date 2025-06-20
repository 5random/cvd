import logging
import pytest
from src.controllers.controller_manager import ControllerManager
from src.controllers.algorithms.motion_detection import MotionDetectionController
from src.controllers.algorithms.reactor_state import ReactorStateController
from src.utils.config_utils.config_service import ConfigurationError
from src.utils.log_utils import log_service


def test_create_known_controller_types():
    manager = ControllerManager()
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
