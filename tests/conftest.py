"""Common pytest fixtures for the test suite."""

from __future__ import annotations

import pytest

@pytest.fixture(autouse=True)
def mute_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Silence logging during tests.

    Several modules import logging helpers from ``log_service`` directly at
    import time.  To avoid noisy output when running tests we patch the common
    logging entry points to simple no-op callables.  ``async_utils`` re-exports
    these functions, so it is patched as well.
    """

    from program.src.utils import log_service
    from program.src.utils.concurrency import async_utils

    for name in ["debug", "info", "warning", "error"]:
        if hasattr(log_service, name):
            monkeypatch.setattr(log_service, name, lambda *a, **k: None)
        if hasattr(async_utils, name):
            monkeypatch.setattr(async_utils, name, lambda *a, **k: None)

    # Also patch any imported logging helpers in already loaded modules
    import sys

    for mod in list(sys.modules.values()):
        mod_name = getattr(mod, "__name__", "")
        if not mod or not mod_name.startswith("program.src."):
            continue
        if mod_name.startswith("src.utils.config_service"):
            # Keep real logging for config service so validation warnings are emitted
            continue
        for name in ["debug", "info", "warning", "error"]:
            if hasattr(mod, name):
                monkeypatch.setattr(mod, name, lambda *a, **k: None, raising=False)


@pytest.fixture(autouse=True)
def restore_data_files(tmp_path):
    """Ensure data files modified during tests are restored."""
    from pathlib import Path
    import shutil

    index_file = Path("data/data_index.json")
    history_file = Path("data/notifications/history.json")
    experiments_dir = Path("data/experiments")

    index_backup = index_file.read_text() if index_file.exists() else None
    history_backup = history_file.read_text() if history_file.exists() else None

    yield

    if index_backup is not None:
        index_file.write_text(index_backup)
    if history_backup is not None:
        history_file.write_text(history_backup)

    if experiments_dir.exists():
        for p in experiments_dir.iterdir():
            if p.is_dir() and p.name.startswith("exp_"):
                shutil.rmtree(p, ignore_errors=True)
