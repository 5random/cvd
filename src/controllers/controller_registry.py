"""Registry for controller types."""

from typing import Dict, Type

from .controller_base import ControllerStage
from .webcam import MotionDetectionController, CameraCaptureController

# Mapping of controller type strings to their implementing classes
CONTROLLER_CLASS_MAP: Dict[str, Type[ControllerStage]] = {}


def register_controller_type(name: str, cls: Type[ControllerStage]) -> None:
    """Register a controller class under a type name."""
    CONTROLLER_CLASS_MAP[name] = cls


# Register built-in controller types
register_controller_type("motion_detection", MotionDetectionController)
register_controller_type("camera", CameraCaptureController)
register_controller_type("camera_capture", CameraCaptureController)

