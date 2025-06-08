import logging
import pytest
from src.controllers.controller_manager import ControllerManager
from src.controllers.algorithms.motion_detection import MotionDetectionController
from src.controllers.algorithms.reactor_state import ReactorStateController
from src.controllers.controller_utils.controller_data_sources.camera_capture_controller import CameraCaptureController


def test_create_known_controller_types():
    manager = ControllerManager()
    md = manager.create_controller({'controller_id': 'md1', 'type': 'motion_detection'})
    rs = manager.create_controller({'controller_id': 'rs1', 'type': 'reactor_state'})
    cam = manager.create_controller({'controller_id': 'cam1', 'type': 'camera_capture'})
    assert isinstance(md, MotionDetectionController)
    assert isinstance(rs, ReactorStateController)
    assert isinstance(cam, CameraCaptureController)


def test_create_controller_missing_required_fields_returns_none(caplog):
    manager = ControllerManager()
    caplog.set_level(logging.WARNING)
    result = manager.create_controller({'controller_id': 'missing_type'})
    assert result is None
    assert any('Unknown controller type' in r.message for r in caplog.records)


def test_create_controller_unknown_type_warns(caplog):
    manager = ControllerManager()
    caplog.set_level(logging.WARNING)
    result = manager.create_controller({'controller_id': 'c1', 'type': 'unknown'})
    assert result is None
    assert any('Unknown controller type' in r.message for r in caplog.records)
