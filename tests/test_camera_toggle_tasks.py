import asyncio
import types

import pytest

from tests.test_alt_gui import (
    simple_gui_app,
    mock_controller_manager,
    mock_config_service,
)
from program.src.controllers.controller_base import ControllerStatus

class DummyButton:
    def set_icon(self, *args, **kwargs):
        pass

    def set_text(self, *args, **kwargs):
        pass

class DummyCameraController:
    def __init__(self):
        self.status = ControllerStatus.STOPPED
        self.start_calls = 0

    async def start(self):
        self.start_calls += 1
        self.status = ControllerStatus.RUNNING

    async def stop(self):
        self.status = ControllerStatus.STOPPED

    async def cleanup(self):
        pass

@pytest.mark.asyncio
async def test_toggle_no_duplicate_capture_tasks(simple_gui_app):
    simple_gui_app.camera_status_icon = types.SimpleNamespace(classes=lambda **k: None)
    simple_gui_app.webcam_stream = types.SimpleNamespace(start_camera_btn=DummyButton())

    cam = DummyCameraController()
    cam.status = ControllerStatus.RUNNING
    simple_gui_app.controller_manager.add_mock_controller("camera_capture", cam)
    simple_gui_app.camera_controller = cam

    simple_gui_app.camera_active = False
    simple_gui_app.toggle_camera()
    await asyncio.sleep(0)

    assert cam.start_calls == 0
