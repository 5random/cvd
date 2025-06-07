import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "program"))

import pytest

from src.controllers.controller_utils.controller_data_sources import camera_capture_controller
from src.controllers.controller_utils.controller_data_sources.camera_capture_controller import CameraCaptureController
from src.controllers.controller_base import ControllerConfig

class DummyCapture:
    def __init__(self, index):
        self.index = index
        self.opened = True
        self.read_calls = 0
    def isOpened(self):
        return True
    def read(self):
        self.read_calls += 1
        if self.read_calls == 1:
            raise RuntimeError("read fail")
        return True, f"frame{self.read_calls}"
    def set(self, prop, value):
        return True
    def release(self):
        self.opened = False

async def immediate(fn, *args, **kwargs):
    return fn(*args, **kwargs)

@pytest.mark.asyncio
async def test_camera_capture_recovery(monkeypatch):
    from src.controllers.controller_utils import controller_data_sources
    cap_module = controller_data_sources.camera_capture_controller

    monkeypatch.setattr(cap_module, "run_camera_io", immediate)
    monkeypatch.setattr(cap_module.cv2, "VideoCapture", lambda idx: DummyCapture(idx))
    monkeypatch.setattr(cap_module, "info", lambda *a, **k: None)
    monkeypatch.setattr(cap_module, "warning", lambda *a, **k: None)
    monkeypatch.setattr(cap_module, "error", lambda *a, **k: None)
    # also suppress logging in controller_base
    import src.controllers.controller_base as controller_base
    monkeypatch.setattr(controller_base, "info", lambda *a, **k: None)
    monkeypatch.setattr(controller_base, "warning", lambda *a, **k: None)
    monkeypatch.setattr(controller_base, "error", lambda *a, **k: None)
    monkeypatch.setattr(controller_base, "debug", lambda *a, **k: None)

    cfg = ControllerConfig(controller_id="cam", controller_type="camera_capture", parameters={"device_index": 0, "fps": 10})
    controller = CameraCaptureController("cam", cfg)
    started = await controller.start()
    assert started
    await asyncio.sleep(0.3)
    frame = controller.get_output()
    assert frame == "frame2"
    try:
        await controller.stop()
    except asyncio.CancelledError:
        pass
    await controller.cleanup()
