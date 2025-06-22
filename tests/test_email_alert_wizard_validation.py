from src.gui.alt_gui.alt_gui_elements.alert_element_new import EmailAlertWizard
from nicegui import ui
import pytest


@pytest.fixture
def dummy_ui(monkeypatch):
    class Dummy:
        def __init__(self, *a, **k):
            self.disabled = False
            self.text = ""

        def classes(self, *a, **k):
            return self

        def props(self, *a, **k):
            return self

        def on(self, *a, **k):
            return self

        def clear(self):
            return self

        def disable(self):
            self.disabled = True

        def enable(self):
            self.disabled = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    for name in ["row", "column", "label", "button", "icon", "card"]:
        monkeypatch.setattr(ui, name, lambda *a, **k: Dummy())

    yield


def test_is_valid_email_tuhh_domain_only():
    wizard = EmailAlertWizard()
    assert wizard._is_valid_email("user@tuhh.de")
    assert wizard._is_valid_email("test.user@tuhh.de")
    assert wizard._is_valid_email("foo+bar-baz@tuhh.de")
    assert not wizard._is_valid_email("user@example.com")
    assert not wizard._is_valid_email("user@tuhh.com")
    assert not wizard._is_valid_email("invalid")


def test_remove_last_recipient_disables_next(dummy_ui):
    wizard = EmailAlertWizard()
    wizard.alert_data["emails"] = ["user@tuhh.de"]

    class DummyList:
        def clear(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    class DummyLabel:
        def __init__(self):
            self.text = ""

        def classes(self, *a, **k):
            return self

    class DummyButton:
        def __init__(self):
            self.disabled = False

        def disable(self):
            self.disabled = True

        def enable(self):
            self.disabled = False

    email_list = DummyList()
    feedback = DummyLabel()
    next_btn = DummyButton()

    wizard._remove_email("user@tuhh.de", email_list, feedback, next_btn)

    assert next_btn.disabled


def test_validate_step2_invalid_emails(dummy_ui):
    wizard = EmailAlertWizard()
    wizard.alert_data["emails"] = ["user@tuhh.de", "bad@example.com"]

    class DummyLabel:
        def __init__(self):
            self.text = ""

        def classes(self, *a, **k):
            return self

    class DummyButton:
        def __init__(self):
            self.disabled = False

        def disable(self):
            self.disabled = True

        def enable(self):
            self.disabled = False

    feedback = DummyLabel()
    next_btn = DummyButton()

    wizard._validate_step2(feedback, next_btn)

    assert next_btn.disabled
    assert "invalid" in feedback.text.lower()


def test_validate_step2_all_valid(dummy_ui):
    wizard = EmailAlertWizard()
    wizard.alert_data["emails"] = ["one@tuhh.de", "two@tuhh.de"]

    class DummyLabel:
        def __init__(self):
            self.text = ""

        def classes(self, *a, **k):
            return self

    class DummyButton:
        def __init__(self):
            self.disabled = False

        def disable(self):
            self.disabled = True

        def enable(self):
            self.disabled = False

    feedback = DummyLabel()
    next_btn = DummyButton()

    wizard._validate_step2(feedback, next_btn)

    assert not next_btn.disabled
    assert feedback.text.startswith("✓")
