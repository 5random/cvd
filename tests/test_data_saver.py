import time
from pathlib import Path

from src.utils.data_utils.data_saver import DataSaver


def test_close_waits_for_background_tasks(tmp_path):
    ds = DataSaver(Path(tmp_path), enable_background_operations=True)
    tasks = list(ds._tasks)
    assert tasks and not tasks[0].done()

    ds.close()

    assert all(t.done() for t in tasks)
    assert ds._tasks == []
