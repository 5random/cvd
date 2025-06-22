import pytest

from src.gui.alt_gui.alt_gui_elements.webcam_stream_element import WebcamStreamElement

class DummyMenuItem:
    def __init__(self):
        self.text = ""
    def set_text(self, text):
        self.text = text

@pytest.fixture
def dummy_ws(monkeypatch):
    ws = WebcamStreamElement.__new__(WebcamStreamElement)
    ws.recording = False
    ws.record_menu_item = DummyMenuItem()
    # disable notify_later to avoid side effects
    monkeypatch.setattr(
        "src.gui.alt_gui.alt_gui_elements.webcam_stream_element.notify_later",
        lambda *a, **k: None,
    )
    return ws

def test_toggle_recording_changes_label(dummy_ws):
    dummy_ws.toggle_recording()
    assert dummy_ws.recording is True
    assert dummy_ws.record_menu_item.text == "Stop Recording"

    dummy_ws.toggle_recording()
    assert dummy_ws.recording is False
    assert dummy_ws.record_menu_item.text == "Start Recording"
