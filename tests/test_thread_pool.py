import threading
import pytest

from src.utils.concurrency.thread_pool import ManagedThreadPool, ThreadPoolConfig
from src.utils.log_utils import log_service


def _hold_event(evt: threading.Event) -> int:
    evt.wait()
    return 1


def test_queue_full_raises(monkeypatch):
    cfg = ThreadPoolConfig(max_workers=1, queue_maxsize=1, queue_block=False)
    pool = ManagedThreadPool(cfg)
    evt = threading.Event()
    fut = pool.submit_task(_hold_event, evt)
    with pytest.raises(RuntimeError):
        pool.submit_task(lambda: 0)
    evt.set()
    fut.result(timeout=1)
    pool.shutdown()


def test_submit_failure_releases_semaphore(monkeypatch):
    cfg = ThreadPoolConfig(max_workers=1, queue_maxsize=1, queue_block=False)
    pool = ManagedThreadPool(cfg)
    pool._ensure_executor()
    monkeypatch.setattr(pool._executor, "submit", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    with pytest.raises(ValueError):
        pool.submit_task(lambda: 1)
    assert pool._sema._value == 1
    pool.shutdown()


def test_task_failure_updates_stats(monkeypatch):
    cfg = ThreadPoolConfig(max_workers=1, queue_maxsize=1, queue_block=False)
    pool = ManagedThreadPool(cfg)

    def failing():
        raise RuntimeError("boom")

    fut = pool.submit_task(failing)
    with pytest.raises(RuntimeError):
        fut.result(timeout=1)
    assert pool._stats.tasks_failed == 1
    assert pool._sema._value == 1
    pool.shutdown()
