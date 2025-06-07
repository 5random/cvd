import json
import os
import time
from pathlib import Path

from nicegui import ui
import pytest

from src.utils.config_utils.config_service import ConfigurationService
from src.utils.log_utils.log_service import LogService
import src.gui.gui_tab_components.gui_tab_log_component as log_component
from src.gui.gui_tab_components.gui_tab_log_component import LogComponent


@pytest.fixture
def minimal_log_service(tmp_path, monkeypatch):
    cfg = {"logging": {"log_dir": str(tmp_path / "logs"), "retention_days": 0}}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    (tmp_path / "default_config.json").write_text("{}")
    service = ConfigurationService(tmp_path / "config.json", tmp_path / "default_config.json")

    logs_dir = tmp_path / "logs"

    def dummy_init(self):
        self.log_level = "INFO"
        self.log_dir = logs_dir
        self.rotation_mb = 1
        self.retention_days = 0
        self._initialized = True

    monkeypatch.setattr(LogService, "_initialize_logging", dummy_init)
    log_service = LogService(service)
    return log_service


def _setup_component(log_service, monkeypatch):
    monkeypatch.setattr(log_component, "get_log_service", lambda: log_service)
    monkeypatch.setattr(LogComponent, "_refresh_log_info", lambda self: None)
    messages = []
    monkeypatch.setattr(ui, "notify", lambda msg, **kwargs: messages.append(msg))
    comp = LogComponent()
    return comp, messages


def test_cleanup_old_logs(monkeypatch, tmp_path, minimal_log_service):
    log_service = minimal_log_service
    old_file = log_service.log_dir / "old.log"
    old_file.parent.mkdir(parents=True, exist_ok=True)
    old_file.write_text("x")
    os.utime(old_file, (time.time() - 1, time.time() - 1))

    comp, messages = _setup_component(log_service, monkeypatch)
    comp._cleanup_old_logs()

    assert not old_file.exists()
    assert any("Old logs cleaned up successfully" in m for m in messages)


def test_compress_logs(monkeypatch, tmp_path, minimal_log_service):
    log_service = minimal_log_service
    log_file = log_service.log_dir / "info.log.1"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("abc")

    comp, messages = _setup_component(log_service, monkeypatch)
    comp._compress_logs()

    compressed = log_service.log_dir / "info.log.1.gz"
    assert compressed.exists()
    assert not log_file.exists()
    assert any("Log compression completed successfully" in m for m in messages)
