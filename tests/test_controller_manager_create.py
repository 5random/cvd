import pytest
from src.controllers.controller_manager import ControllerManager
from src.utils.config_utils.config_service import ConfigurationError


def test_create_controller_missing_id():
    manager = ControllerManager("t")
    with pytest.raises(ConfigurationError):
        manager.create_controller({"type": "camera_capture"})


def test_create_controller_missing_type():
    manager = ControllerManager("t")
    with pytest.raises(ConfigurationError):
        manager.create_controller({"controller_id": "c1"})


def test_create_controller_valid():
    manager = ControllerManager("t")
    ctrl = manager.create_controller({"controller_id": "c1", "type": "camera_capture"})
    assert ctrl is not None
    assert ctrl.controller_id == "c1"
