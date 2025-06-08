import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from src.utils.config_utils.config_service import ConfigurationService
from src.utils.log_utils.log_service import LogService
from src.gui.gui_elements.gui_notification_center_element import NotificationCenter

@pytest.fixture
def minimal_services(tmp_path, monkeypatch):
    cfg = {"logging": {"log_dir": str(tmp_path / "logs"), "retention_days": 0}}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    (tmp_path / "default_config.json").write_text("{}")
    config_service = ConfigurationService(tmp_path / "config.json", tmp_path / "default_config.json")

    logs_dir = tmp_path / "logs"

    def dummy_init(self):
        self.log_level = "INFO"
        self.log_dir = logs_dir
        self.rotation_mb = 1
        self.retention_days = 0
        self._initialized = True

    monkeypatch.setattr(LogService, "_initialize_logging", dummy_init)
    log_service = LogService(config_service)

    monkeypatch.setattr(
        "src.gui.gui_elements.gui_notification_center_element.get_log_service",
        lambda: log_service,
    )
    return config_service, log_service

def test_check_log_notifications_uses_configured_dir(minimal_services, monkeypatch):
    config_service, log_service = minimal_services
    monkeypatch.setattr(NotificationCenter, "_setup_monitoring", lambda self: None)
    center = NotificationCenter(config_service)

    error_log = log_service.log_dir / "error.log"
    error_log.parent.mkdir(parents=True, exist_ok=True)
    msg = "Unique test error"
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} - cvd_tracker.error - ERROR - test.py:1 - func - {msg}\n"
    error_log.write_text(line)

    center._last_log_check = 0
    center._check_log_notifications()

    assert any(msg in n.message for n in center.notifications)
