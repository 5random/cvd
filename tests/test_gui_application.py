from pathlib import Path
import pytest
from nicegui import Client, app
import numpy as np
from src.utils.log_utils import log_service

pytest_plugins = ['nicegui.testing.user_plugin']

from src.utils.container import ApplicationContainer

@pytest.mark.asyncio
async def test_gui_pages(user):
    container = ApplicationContainer.create(Path('program/config'))
    with Client.auto_index_client:
        container.web_application.register_components()
    await user.open('/')
    await user.should_see('Dashboard')
    await user.open('/sensors')
    await user.should_see('Sensor Management')
    container.shutdown_sync()


@pytest.mark.asyncio
async def test_video_feed_disconnect(monkeypatch):
    for name in ["debug", "info", "warning", "error"]:
        monkeypatch.setattr(log_service, name, lambda *a, **k: None)

    container = ApplicationContainer.create(Path('program/config'))
    with Client.auto_index_client:
        container.web_application.register_components()

    # provide dummy camera
    class DummyCam:
        update_interval = 0.01

        def get_latest_frame(self):
            return np.zeros((1, 1, 3), dtype=np.uint8)

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
    container.shutdown_sync()
