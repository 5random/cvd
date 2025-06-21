import json
import os
import time
from pathlib import Path

from nicegui import ui
import pytest

from src.utils.config_service import ConfigurationService
from src.utils.log_service import LogService
import program.src.gui.gui_tab_components.gui_tab_log_component as log_component
from program.src.gui.gui_tab_components.gui_tab_log_component import (
    LogComponent,
    LogViewerComponent,
    LogFileInfo,
    ComponentConfig,
)
from datetime import datetime


@pytest.fixture
def minimal_log_service(tmp_path, monkeypatch):
    cfg = {"logging": {"log_dir": str(tmp_path / "logs"), "retention_days": 0}}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    (tmp_path / "default_config.json").write_text("{}")
    service = ConfigurationService(
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


@pytest.mark.parametrize("ext", [".gz", ".bz2", ".xz", ".zip"])
def test_compress_logs_skips_existing(monkeypatch, tmp_path, minimal_log_service, ext):
    """Ensure compress_old_logs ignores already compressed files."""
    log_service = minimal_log_service
    log_file = log_service.log_dir / f"info.log.1{ext}"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("abc")

    log_service.compress_old_logs()

    assert log_file.exists()
    extra = log_service.log_dir / f"info.log.1{ext}.gz"
    assert not extra.exists()


def _create_log_viewer(tmp_path: Path, name: str = "info.log") -> LogViewerComponent:
    log_file = tmp_path / name
    info = LogFileInfo(
        name=name,
        path=log_file,
        size_bytes=0,
        size_mb=0.0,
        modified=datetime.now(),
        log_type="info",
        is_compressed=False,
    )
    return LogViewerComponent(ComponentConfig(name), info)


def test_log_viewer_reads_incrementally(tmp_path: Path):
    viewer = _create_log_viewer(tmp_path)
    log_path = viewer.log_file_info.path
    log_path.write_text("a\n")

    viewer._load_log_content()
    assert viewer._log_lines == ["a\n"]
    first_offset = viewer._file_offset

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("b\n")

    viewer._load_log_content()
    assert viewer._log_lines == ["a\n", "b\n"]
    assert viewer._file_offset > first_offset


def test_log_viewer_resets_on_rotation(tmp_path: Path):
    viewer = _create_log_viewer(tmp_path)
    log_path = viewer.log_file_info.path
    log_path.write_text("a\n")
    viewer._load_log_content()

    log_path.write_text("")
    viewer._load_log_content()

    log_path.write_text("c\n")
    viewer._load_log_content()

    assert viewer._log_lines == ["c\n"]
