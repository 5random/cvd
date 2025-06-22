from src.gui.alt_gui.alt_gui_elements.alert_element_new import (
    EmailAlertStatusDisplay,
)


def test_anonymize_email_local_part_only():
    display = EmailAlertStatusDisplay([])
    assert display.anonymize_email("user.username@tuhh.de") == "u**r.u*****e@tuhh.de"
    assert display.anonymize_email("ab@tuhh.de") == "a*@tuhh.de"
    assert display.anonymize_email("a@tuhh.de") == "*@tuhh.de"
