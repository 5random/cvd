import types
from nicegui import ui
from cvd.gui.alt_gui_elements.webcam_stream_element import WebcamStreamElement


def test_webcam_stream_initializes_and_updates_status(monkeypatch):
    # simple page decorator to avoid nicegui routing
    monkeypatch.setattr(ui, "page", lambda *a, **k: (lambda f: f))
    WebcamStreamElement._page_registered = False
    states = []
    ws = WebcamStreamElement(settings={}, on_camera_status_change=states.append)
    assert ws.camera_active is False
    ws.camera_active = True
    ws._update_status()
    assert states == [True]
