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

    from src.utils.log_utils import log_service
    from src.utils.concurrency import async_utils

    for name in ["debug", "info", "warning", "error"]:
        if hasattr(log_service, name):
            monkeypatch.setattr(log_service, name, lambda *a, **k: None)
        if hasattr(async_utils, name):
            monkeypatch.setattr(async_utils, name, lambda *a, **k: None)

