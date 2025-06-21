import threading
import time
import pytest

from src.utils.concurrency.thread_pool import ManagedThreadPool, ThreadPoolConfig
from src.utils import log_service


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
    monkeypatch.setattr(
        pool._executor,
        "submit",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")),
    )
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


def test_thread_pool_circuit_breaker():
    cfg = ThreadPoolConfig(
        max_workers=1,
        queue_maxsize=1,
        queue_block=False,
        circuit_breaker_failures=1,
        circuit_breaker_reset_timeout=0.1,
    )
    pool = ManagedThreadPool(cfg)

    def failing():
        raise RuntimeError("boom")

    fut = pool.submit_task(failing)
    with pytest.raises(RuntimeError):
        fut.result(timeout=1)

    with pytest.raises(RuntimeError, match="Circuit breaker open – task rejected"):
        pool.submit_task(lambda: 1)

    time.sleep(cfg.circuit_breaker_reset_timeout + cfg.hysteresis_seconds + 0.1)

    fut2 = pool.submit_task(lambda: 2)
    assert fut2.result(timeout=1) == 2
    pool.shutdown()
