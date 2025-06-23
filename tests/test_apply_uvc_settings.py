import cv2
import pytest

from cvd.controllers.camera_utils import apply_uvc_settings
from cvd.controllers.webcam import CameraCaptureController, MotionDetectionController
from cvd.controllers.controller_base import ControllerConfig


class DummyCapture:
    def __init__(self):
        self.calls = []

    def set(self, prop, value):
        self.calls.append((prop, value))
        return True


async def immediate(fn, *args, **kwargs):
    return fn(*args, **kwargs)


@pytest.mark.asyncio
async def test_apply_backlight_compensation(monkeypatch):
    cap = DummyCapture()
    monkeypatch.setattr("cvd.controllers.camera_utils.run_camera_io", immediate)
    await apply_uvc_settings(cap, {"backlight_compensation": 3})
    assert (cv2.CAP_PROP_BACKLIGHT, 3.0) in cap.calls


@pytest.mark.asyncio
async def test_camera_controller_apply_uvc(monkeypatch):
    cap = DummyCapture()
    applied = {}

    async def dummy_apply(capture, settings, controller_id=None):
        applied["capture"] = capture
        applied["settings"] = settings
        applied["controller_id"] = controller_id

    monkeypatch.setattr(
        "cvd.controllers.webcam.camera_capture_controller.apply_uvc_settings",
        dummy_apply,
    )
    ctrl = CameraCaptureController(
        "cam",
        ControllerConfig(controller_id="cam", controller_type="camera_capture"),
    )
    ctrl._capture = cap
    await ctrl.apply_uvc_settings({"brightness": 2})
    assert applied["capture"] is cap
    assert applied["settings"] == {"brightness": 2}
    assert applied["controller_id"] == "cam"


@pytest.mark.asyncio
async def test_motion_controller_apply_uvc_defaults(monkeypatch):
    cap = DummyCapture()
    applied = {}

    async def dummy_apply(capture, settings, controller_id=None):
        applied["capture"] = capture
        applied["settings"] = settings
        applied["controller_id"] = controller_id

    monkeypatch.setattr(
        "cvd.controllers.webcam.motion_detection.apply_uvc_settings",
        dummy_apply,
    )
    cfg = ControllerConfig(controller_id="md", controller_type="motion_detection")
    ctrl = MotionDetectionController("md", cfg)
    ctrl._capture = cap
    ctrl.uvc_settings = {"gain": 1}
    await ctrl.apply_uvc_settings()
    assert applied["capture"] is cap
    assert applied["settings"] == {"gain": 1}
    assert applied["controller_id"] == "md"
