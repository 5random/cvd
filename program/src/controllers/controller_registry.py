from typing import Dict, Type

from .controller_base import ControllerStage
from .algorithms.motion_detection import MotionDetectionController
from .algorithms.reactor_state import ReactorStateController
from .controller_utils.controller_data_sources.camera_capture_controller import CameraCaptureController

# Mapping of controller type strings to their implementing classes
CONTROLLER_CLASS_MAP: Dict[str, Type[ControllerStage]] = {
    "motion_detection": MotionDetectionController,
    "reactor_state": ReactorStateController,
    "camera_capture": CameraCaptureController,
}

