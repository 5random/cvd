import cv2
import pytest

from src.controllers.camera_utils import apply_uvc_settings


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
    monkeypatch.setattr("src.controllers.camera_utils.run_camera_io", immediate)
    await apply_uvc_settings(cap, {"backlight_compensation": 3})
    assert (cv2.CAP_PROP_BACKLIGHT, 3.0) in cap.calls
