import asyncio
import pytest

from cvd.controllers.controller_base import ControllerConfig
from cvd.controllers.webcam.camera_capture_controller import CameraCaptureController
from cvd.controllers.webcam import base_camera_capture as base_mod


@pytest.mark.asyncio
async def test_start_capture_only_once(monkeypatch):
    monkeypatch.setattr(base_mod, "info", lambda *a, **k: None)

    start_count = {"count": 0}

    async def fake_loop(self):
        start_count["count"] += 1
        try:
            await self._stop_event.wait()
        except asyncio.CancelledError:
            raise

    monkeypatch.setattr(CameraCaptureController, "_capture_loop", fake_loop)

    cfg = ControllerConfig(controller_id="cam", controller_type="camera_capture")
    ctrl = CameraCaptureController("cam", cfg)

    ctrl.start_capture()
    await asyncio.sleep(0)
    first = ctrl._capture_task
    ctrl.start_capture()
    await asyncio.sleep(0)
    second = ctrl._capture_task

    assert first is second
    assert start_count["count"] == 1

    await ctrl.stop_capture()

