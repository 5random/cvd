import pytest

from cvd.gui.alt_gui.alt_gui_elements.webcam_stream_element import WebcamStreamElement

@pytest.fixture
def dummy_ws(monkeypatch):
    ws = WebcamStreamElement.__new__(WebcamStreamElement)
    ws.recording = False
    # disable notify_later to avoid side effects
    monkeypatch.setattr(
        "cvd.gui.alt_gui_elements.webcam_stream_element.notify_later",
        lambda *a, **k: None,
    )
    return ws

def test_toggle_recording_is_noop(dummy_ws):
    dummy_ws.toggle_recording()
    assert dummy_ws.recording is False
