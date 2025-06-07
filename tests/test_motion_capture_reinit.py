import asyncio
import pytest

from src.controllers.algorithms.motion_detection import MotionDetectionController
from src.controllers.controller_base import ControllerConfig

class DummyCapture:
    def __init__(self, index):
        self.index = index
        self.opened = True

    def isOpened(self):
        return self.opened

    def read(self):
        return True, "frame"

    def set(self, prop, value):
        return True

    def release(self):
        self.opened = False

async def immediate(fn, *args, **kwargs):
    return fn(*args, **kwargs)

@pytest.mark.asyncio
async def test_reinitialize_on_none(monkeypatch):
    from src.controllers.algorithms import motion_detection as md_module

    monkeypatch.setattr(md_module, "run_camera_io", immediate)
    first = DummyCapture(0)
    second = DummyCapture(0)
    monkeypatch.setattr(md_module.cv2, "VideoCapture", lambda idx: first)
    for name in ["info", "warning", "error", "debug"]:
        if hasattr(md_module, name):
            monkeypatch.setattr(md_module, name, lambda *a, **k: None)
    import src.controllers.controller_base as controller_base
    for name in ["info", "warning", "error", "debug"]:
        monkeypatch.setattr(controller_base, name, lambda *a, **k: None)

    cfg = ControllerConfig(controller_id="md", controller_type="motion_detection", parameters={"device_index": 0, "fps": 10})
    controller = MotionDetectionController("md", cfg)
    monkeypatch.setattr(controller._motion_pool, "submit_async", immediate)
    started = await controller.start()
    assert started
    controller._capture = None
    monkeypatch.setattr(md_module.cv2, "VideoCapture", lambda idx: second)
    await asyncio.sleep(0.2)
    assert controller._capture is second
    try:
        await controller.stop()
    except asyncio.CancelledError:
        pass
    try:
        await controller.cleanup()
    except asyncio.CancelledError:
        pass
