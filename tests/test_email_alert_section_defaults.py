import pytest
from src.gui.alt_gui.alt_gui_elements.alert_element import EmailAlertsSection
from nicegui import ui


def test_email_alert_defaults(monkeypatch):
    # patch ui.page decorator to avoid registering routes
    monkeypatch.setattr(ui, "page", lambda *a, **k: (lambda f: f))
    section = EmailAlertsSection({})
    assert section.settings["email"] == "user@example.com"
    assert section.settings["alert_delay"] == 5

