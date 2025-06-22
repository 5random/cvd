from pathlib import Path
import pytest
from nicegui import Client, app
import numpy as np
import cv2
from src.utils import log_service

pytest_plugins = ['nicegui.testing.user_plugin']

from program.src.utils.container import ApplicationContainer

@pytest.mark.asyncio
async def test_gui_pages(user):
    container = ApplicationContainer.create(Path('program/config'))
    with Client.auto_index_client:
        container.web_application.register_components()
    await user.open('/')
    await user.should_see('Dashboard')
    await user.open('/sensors')
    await user.should_see('Sensor Management')
    await container.shutdown()


@pytest.mark.asyncio
async def test_video_feed_disconnect(monkeypatch):
    for name in ["debug", "info", "warning", "error"]:
        monkeypatch.setattr(log_service, name, lambda *a, **k: None)

    container = ApplicationContainer.create(Path('program/config'))
    with Client.auto_index_client:
        container.web_application.register_components()

    # provide dummy camera
    class DummyCam:
        component_id = "dummy_cam"
        update_interval = 0.01

        def get_latest_frame(self):
            return np.zeros((10, 10, 3), dtype=np.uint8)

    container.web_application.component_registry._components[
        'dashboard_camera_stream'
    ] = DummyCam()

    route = [r for r in app.routes if getattr(r, 'path', None) == '/video_feed/{cid}'][0]
    endpoint = route.endpoint.__wrapped__

    class DummyRequest:
        async def is_disconnected(self):
            return True

    response = await endpoint(request=DummyRequest(), cid='dashboard_camera_stream')
    gen = response.body_iterator
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()
    await container.shutdown()


@pytest.mark.asyncio
async def test_video_feed_creates_temp_camera(monkeypatch):
    """Ensure a temporary camera stream is created when none is registered."""
    for name in ["debug", "info", "warning", "error"]:
        monkeypatch.setattr(log_service, name, lambda *a, **k: None)

    class DummyCam:
        component_id = "dummy_cam"
        update_interval = 0.01

        def __init__(self, *a, **k):
            pass

        def get_latest_frame(self):
            return np.zeros((10, 10, 3), dtype=np.uint8)

        def start_streaming(self):
            pass

        def cleanup(self):
            pass

    monkeypatch.setattr(
        "program.src.gui.application.CameraStreamComponent",
        DummyCam,
    )
    monkeypatch.setattr(
        cv2,
        "imencode",
        lambda ext, frame: (True, np.zeros(1, dtype=np.uint8)),
    )

    container = ApplicationContainer.create(Path("program/config"))
    with Client.auto_index_client:
        container.web_application.register_components()

    route = [r for r in app.routes if getattr(r, "path", None) == "/video_feed"][0]
    endpoint = route.endpoint.__wrapped__

    class DummyRequest:
        def __init__(self):
            self.count = 0

        async def is_disconnected(self):
            self.count += 1
            return self.count > 1

    response = await endpoint(request=DummyRequest())
    gen = response.body_iterator
    await gen.__anext__()
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

    assert container.web_application._temp_camera_stream is not None

    await container.web_application.shutdown()

    assert container.web_application._temp_camera_stream is None
    assert (
        "temp_camera_stream" not in container.web_application.component_registry._components
    )

    await container.shutdown()
