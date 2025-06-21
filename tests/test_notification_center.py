import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from src.utils.config_service import ConfigurationService
from src.utils.log_service import LogService
from src.gui.gui_elements.gui_notification_center_element import (
    NotificationCenter,
    NotificationSeverity,
    NotificationSource,
)


@pytest.fixture
def minimal_services(tmp_path, monkeypatch):
    cfg = {"logging": {"log_dir": str(tmp_path / "logs"), "retention_days": 0}}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    (tmp_path / "default_config.json").write_text("{}")
    config_service = ConfigurationService(
        tmp_path / "config.json", tmp_path / "default_config.json"
    )

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


@pytest.fixture
def notification_center(tmp_path, minimal_services, monkeypatch):
    config_service, _ = minimal_services
    monkeypatch.setattr(NotificationCenter, "_setup_monitoring", lambda self: None)
    monkeypatch.setattr(NotificationCenter, "_update_ui", lambda self: None)
    center = NotificationCenter(config_service)
    center.notification_history_file = tmp_path / "history.json"
    center.notifications.clear()
    return center


@pytest.fixture
def populated_center(notification_center):
    center = notification_center
    ids = [
        center.add_notification(
            "n1",
            "m1",
            severity=NotificationSeverity.INFO,
            source=NotificationSource.SYSTEM,
        ),
    ]
    time.sleep(0.01)
    ids.append(
        center.add_notification(
            "n2",
            "m2",
            severity=NotificationSeverity.ERROR,
            source=NotificationSource.SENSOR,
        )
    )
    time.sleep(0.01)
    ids.append(
        center.add_notification(
            "n3",
            "m3",
            severity=NotificationSeverity.WARNING,
            source=NotificationSource.SYSTEM,
        )
    )

    return center, ids


def test_mark_as_read_and_filtering(populated_center):
    center, ids = populated_center

    assert center.get_unread_count() == 3

    center.mark_as_read(ids[0])

    assert center.get_unread_count() == 2
    assert next(n for n in center.notifications if n.id == ids[0]).read

    center._severity_filter = "error"
    filtered = center._get_filtered_notifications()
    assert [n.id for n in filtered] == [ids[1]]

    center._severity_filter = "all"
    center._source_filter = "sensor"
    filtered = center._get_filtered_notifications()
    assert [n.id for n in filtered] == [ids[1]]


def test_mark_all_and_clear_notifications(populated_center):
    center, _ = populated_center

    center.mark_all_as_read()
    assert center.get_unread_count() == 0
    assert all(n.read for n in center.notifications)

    center.clear_notifications()
    assert center.notifications == []


def test_notification_history_persistence(
    notification_center, minimal_services, monkeypatch
):
    center = notification_center
    ids = [
        center.add_notification(
            "t1",
            "m1",
            severity=NotificationSeverity.INFO,
            source=NotificationSource.SYSTEM,
        )
    ]
    time.sleep(0.01)
    ids.append(
        center.add_notification(
            "t2",
            "m2",
            severity=NotificationSeverity.ERROR,
            source=NotificationSource.SYSTEM,
        )
    )
    center.mark_as_read(ids[0])

    center._save_notification_history()
    assert center.notification_history_file.exists()

    config_service, _ = minimal_services
    new_center = NotificationCenter(config_service)
    new_center.notification_history_file = center.notification_history_file
    new_center.notifications.clear()
    new_center._load_notification_history()

    loaded = {n.id: n for n in new_center.notifications}
    assert set(loaded.keys()) == set(ids)
    assert loaded[ids[0]].read is True
    assert loaded[ids[1]].read is False


def test_init_uses_configuration(tmp_path, monkeypatch):
    cfg = {
        "logging": {"log_dir": str(tmp_path / "logs"), "retention_days": 0},
        "ui": {
            "notification_center": {
                "max_notifications": 10,
                "history_file": str(tmp_path / "history.json"),
                "update_interval_s": 3,
            }
        },
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    (tmp_path / "default_config.json").write_text("{}")
    config_service = ConfigurationService(
        tmp_path / "config.json", tmp_path / "default_config.json"
    )

    monkeypatch.setattr(LogService, "_initialize_logging", lambda self: None)
    monkeypatch.setattr(NotificationCenter, "_setup_monitoring", lambda self: None)
    monkeypatch.setattr(
        "src.gui.gui_elements.gui_notification_center_element.get_log_service",
        lambda: LogService(config_service),
    )

    center = NotificationCenter(config_service)

    assert center.max_notifications == 10
    assert center.notification_history_file == Path(tmp_path / "history.json")
    assert center.check_interval == 3
