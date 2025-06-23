import pytest

from src.utils.alert_system_utils.email_alert_service import EmailAlertService


class DummyConfigService:
    def __init__(self, cfg: dict) -> None:
        self._cfg = cfg

    def get(self, path: str, _type=None, default=None):
        value = self._cfg
        for key in path.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        if _type is not None and not isinstance(value, _type):
            return default
        return value


def test_recipient_property_accessible_after_init():
    service = EmailAlertService(DummyConfigService({"alerting": {}}))
    assert service.recipient is None
