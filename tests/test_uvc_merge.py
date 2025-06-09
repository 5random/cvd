import json
import pytest
from pathlib import Path

from src.utils.config_utils.config_service import ConfigurationService, set_config_service
from src.controllers.controller_base import ControllerConfig
from src.controllers.controller_utils.controller_data_sources.camera_capture_controller import CameraCaptureController
from src.controllers.algorithms.motion_detection import MotionDetectionController


@pytest.mark.parametrize("controller_cls, ctrl_type", [
    (CameraCaptureController, "camera_capture"),
    (MotionDetectionController, "motion_detection"),
])
def test_webcam_config_uvc_only(tmp_path: Path, controller_cls, ctrl_type):
    cfg_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config = {
        "webcams": [
            {"cam1": {"name": "cam1", "device_index": 0, "uvc": {"brightness": 42}}}
        ]
    }
    cfg_path.write_text(json.dumps(config))
    default_path.write_text("{}")

    service = ConfigurationService(cfg_path, default_path)
    set_config_service(service)

    cfg = ControllerConfig(controller_id="c1", controller_type=ctrl_type, parameters={"cam_id": "cam1"})
    ctrl = controller_cls("c1", cfg)
    assert ctrl.uvc_settings == {"brightness": 42}
    set_config_service(None)


@pytest.mark.parametrize("controller_cls, ctrl_type", [
    (CameraCaptureController, "camera_capture"),
    (MotionDetectionController, "motion_detection"),
])
def test_webcam_config_merge_uvc_and_settings(tmp_path: Path, controller_cls, ctrl_type):
    cfg_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config = {
        "webcams": [
            {
                "cam1": {
                    "name": "cam1",
                    "device_index": 0,
                    "uvc": {"brightness": 1, "contrast": 2},
                    "uvc_settings": {"contrast": 3}
                }
            }
        ]
    }
    cfg_path.write_text(json.dumps(config))
    default_path.write_text("{}")

    service = ConfigurationService(cfg_path, default_path)
    set_config_service(service)

    cfg = ControllerConfig(controller_id="c1", controller_type=ctrl_type, parameters={"cam_id": "cam1"})
    ctrl = controller_cls("c1", cfg)
    assert ctrl.uvc_settings["brightness"] == 1
    assert ctrl.uvc_settings["contrast"] == 3
    set_config_service(None)
