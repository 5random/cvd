from program.src.gui.alt_gui.alt_gui_elements.alert_element_new import EmailAlertWizard


def test_is_valid_email_tuhh_domain_only():
    wizard = EmailAlertWizard()
    assert wizard._is_valid_email("user@tuhh.de")
    assert not wizard._is_valid_email("user@example.com")
    assert not wizard._is_valid_email("user@tuhh.com")
    assert not wizard._is_valid_email("invalid")
