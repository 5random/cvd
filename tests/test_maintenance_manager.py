import time

from src.utils.data_utils.maintenance import MaintenanceManager
from src.utils.concurrency.thread_pool import get_thread_pool_manager, ThreadPoolType


class DummyManager:
    pass


def test_background_task_tracking():
    mm = MaintenanceManager(DummyManager())
    pool = get_thread_pool_manager().get_pool(ThreadPoolType.GENERAL)

    fut = pool.submit_task(lambda: None, task_id="dummy")
    mm._track(pool, fut)

    fut.result(timeout=1)
    time.sleep(0.05)
    assert not mm._background_tasks
