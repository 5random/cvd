
from nicegui import ui
from src.gui.ui_helpers import notify_later


class DummyElement:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_notify_later(monkeypatch):
    timer_calls = []
    notify_calls = []

    def fake_timer(interval, callback, *, active=True, once=False, immediate=True):
        timer_calls.append(
            {
                "interval": interval,
                "callback": callback,
                "active": active,
                "once": once,
                "immediate": immediate,
            }
        )

    def fake_notify(message, **kwargs):
        notify_calls.append((message, kwargs))

    monkeypatch.setattr(ui, "timer", fake_timer)
    monkeypatch.setattr(ui, "notify", fake_notify)

    notify_later("msg")
    assert len(timer_calls) == 1
    assert timer_calls[0]["once"] is True

    timer_calls[0]["callback"]()
    assert notify_calls == [("msg", {})]

    timer_calls.clear()
    notify_calls.clear()
    dummy_slot = DummyElement()

    notify_later("msg", slot=dummy_slot)
    assert len(timer_calls) == 1
    assert timer_calls[0]["once"] is True

    timer_calls[0]["callback"]()
    assert notify_calls == [("msg", {})]
