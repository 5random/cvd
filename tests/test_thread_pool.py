import threading
import time
import asyncio
import pytest

from cvd.utils.concurrency.thread_pool import (
    ManagedThreadPool,
    ThreadPoolConfig,
    get_thread_pool_manager,
    ThreadPoolType,
)


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


def test_get_thread_pool_manager_default_workers(monkeypatch):
    from cvd.utils import concurrency

    monkeypatch.setattr(concurrency.thread_pool, "_global_mgr", None)

    mgr = get_thread_pool_manager(default_max_workers=1)
    pool = mgr.get_pool(ThreadPoolType.GENERAL)
    assert pool._workers == 1
    asyncio.run(mgr.shutdown_all())
    monkeypatch.setattr(concurrency.thread_pool, "_global_mgr", None)


def test_container_applies_thread_pool_max_workers(tmp_path, monkeypatch):
    import json
    from cvd.utils.container import ApplicationContainer

    monkeypatch.setattr(
        "cvd.utils.concurrency.thread_pool._global_mgr", None
    )

    # Patch heavy UI elements to lightweight stubs for initialization
    class DummyWebApp:
        def __init__(self, *a, **k):
            from types import SimpleNamespace

            self.component_registry = SimpleNamespace(cleanup_all=lambda: None)

        async def startup(self):
            pass

        async def shutdown(self):
            pass

        def register_components(self):
            pass

    monkeypatch.setattr(
        "cvd.gui.alt_application.SimpleGUIApplication", DummyWebApp
    )

    cfg = {
        "thread_pool": {"max_workers": 1},
        "data_storage": {"storage_paths": {"base": str(tmp_path / "data")}},
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    (tmp_path / "default_config.json").write_text("{}")

    container = ApplicationContainer.create(tmp_path)
    try:
        pool = get_thread_pool_manager().get_pool(ThreadPoolType.GENERAL)
        assert pool._workers == 1
    finally:
        container.shutdown_sync()
        asyncio.run(get_thread_pool_manager().shutdown_all())
        monkeypatch.setattr(
            "cvd.utils.concurrency.thread_pool._global_mgr", None
        )
