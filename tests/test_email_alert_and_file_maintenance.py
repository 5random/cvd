import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.utils.alert_system_utils.email_alert_service import EmailAlertService
from src.utils.data_utils.file_management_service import FileMaintenanceService


class DummyConfigService:
    def __init__(self, cfg: dict):
        self._cfg = cfg

    def get(self, path: str, _type=None, default=None):
        value = self._cfg
        for key in path.split('.'):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        if _type is not None and not isinstance(value, _type):
            return default
        return value


class DummySMTP:
    instances = []

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.starttls_called = False
        self.login_args = None
        self.sent_messages = []
        DummySMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def starttls(self):
        self.starttls_called = True

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, msg):
        self.sent_messages.append(msg)


class DummyFuture:
    def __init__(self, result):
        self._result = result

    def result(self):
        return self._result


class DummyPool:
    def submit_task(self, fn, *args, **kwargs):
        kwargs.pop("task_id", None)
        return DummyFuture(fn(*args, **kwargs))


# ---------------------- EmailAlertService tests ----------------------

def test_send_alert_success(monkeypatch):
    cfg = {
        'alerting': {
            'email_recipient': 'dest@example.com',
            'smtp_host': 'smtp.host',
            'smtp_port': 587,
            'smtp_user': 'sender@example.com',
            'smtp_password': 'pw',
            'critical_state_timeout_s': 30,
        }
    }
    service = EmailAlertService(DummyConfigService(cfg))
    monkeypatch.setattr('smtplib.SMTP', DummySMTP)

    result = service.send_alert('sub', 'body')

    assert result is True
    assert DummySMTP.instances
    smtp = DummySMTP.instances[-1]
    assert smtp.host == 'smtp.host'
    assert smtp.port == 587
    assert smtp.starttls_called
    assert smtp.login_args == ('sender@example.com', 'pw')
    assert smtp.sent_messages
    msg = smtp.sent_messages[0]
    assert msg['To'] == 'dest@example.com'
    assert msg['From'] == 'sender@example.com'


def test_send_alert_no_recipient(monkeypatch):
    cfg = {'alerting': {}}
    service = EmailAlertService(DummyConfigService(cfg))
    DummySMTP.instances.clear()
    monkeypatch.setattr('smtplib.SMTP', DummySMTP)

    result = service.send_alert('a', 'b')

    assert result is False
    assert not DummySMTP.instances


# ---------------- FileMaintenanceService tests ----------------------

def test_rotate_old_files(tmp_path: Path, monkeypatch):
    old_file = tmp_path / 'data.csv'
    old_file.write_text('x')
    past = time.time() - 10
    os.utime(old_file, (past, past))

    def get_mgr():
        return SimpleNamespace(get_pool=lambda t: DummyPool())

    monkeypatch.setattr('src.utils.data_utils.file_management_service.get_thread_pool_manager', get_mgr)

    service = FileMaintenanceService(None, compression_threshold_bytes=0, max_file_age_seconds=1)
    service.rotate_old_files([tmp_path])

    compressed_dir = tmp_path / 'compressed'
    rotated = list(compressed_dir.glob('data_*.csv'))
    assert rotated
    assert not old_file.exists()


def test_compress_directory_delegates(tmp_path: Path):
    class DummyCompression:
        def __init__(self):
            self.calls = []

        def compress_directory(self, directory, pattern='*', data_type='general', recursive=True):
            self.calls.append((Path(directory), pattern, data_type, recursive))
            return [Path(directory) / 'out.gz']

    dummy = DummyCompression()
    service = FileMaintenanceService(dummy, compression_threshold_bytes=0, max_file_age_seconds=0)

    result = service.compress_directory(tmp_path, pattern='*.csv', data_type='d', recursive=True)

    assert result == [tmp_path / 'out.gz']
    assert dummy.calls == [(tmp_path, '*.csv', 'd', True)]
