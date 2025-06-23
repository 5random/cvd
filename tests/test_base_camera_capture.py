import asyncio
import pytest

from src.controllers.controller_base import ControllerConfig, ControllerStage
from src.controllers.webcam.base_camera_capture import BaseCameraCapture


class DummyCaptureController(BaseCameraCapture, ControllerStage):
    async def handle_frame(self, frame):
        pass

    def __init__(self):
        cfg = ControllerConfig(controller_id="cam", controller_type="camera_capture")
        super().__init__("cam", cfg)


@pytest.mark.asyncio
async def test_start_capture_idempotent(monkeypatch):
    controller = DummyCaptureController()

    async def dummy_loop(self):
        try:
            await self._stop_event.wait()
        except asyncio.CancelledError:
            pass

    monkeypatch.setattr(controller, "_capture_loop", dummy_loop.__get__(controller, DummyCaptureController))

    create_calls = {"count": 0}
    orig_create_task = asyncio.create_task

    def fake_create_task(coro, *args, **kwargs):
        create_calls["count"] += 1
        return orig_create_task(coro)

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)

    controller.start_capture()
    first_task = controller._capture_task
    controller.start_capture()

    assert controller._capture_task is first_task
    assert create_calls["count"] == 1

    await controller.stop_capture()
