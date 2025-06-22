import os
import logging
from pathlib import Path
import time
import threading


from src.utils.data_utils import data_saver as ds_module
from src.data_handler.interface.sensor_interface import (
    SensorReading,
    SensorStatus,
)


class DummyCompressionService:
    def __init__(self):
        self.calls = []

    def compress_file(self, src: str, dst: str):
        # simply copy the input to the destination
        with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
            fdst.write(fsrc.read())
        self.calls.append((src, dst))
        return Path(dst)


def create_reading(sensor_id: str = "s1") -> SensorReading:
    return SensorReading(sensor_id, 1.0, time.time(), SensorStatus.OK)


def test_data_saver_sync_compression(tmp_path, monkeypatch, caplog):
    dummy = DummyCompressionService()
    monkeypatch.setattr(ds_module, "get_compression_service", lambda: dummy)

    caplog.set_level(logging.WARNING, logger="cvd_tracker.error")

    saver = ds_module.DataSaver(
        base_output_dir=tmp_path,
        compression_threshold_mb=0.0001,
        enable_background_operations=False,
        flush_interval=1,
    )

    for _ in range(20):
        saver.save(create_reading())

    saver.flush_all()

    compressed_dir = tmp_path / "raw" / "compressed"
    compressed_files = list(compressed_dir.glob("*.csv.gz"))
    assert compressed_files, "expected compressed file"
    assert not saver._tasks, "no background tasks when disabled"
    saver.close()


def test_data_saver_no_compression_available(tmp_path, monkeypatch):
    def raise_error():
        raise RuntimeError("compression unavailable")

    monkeypatch.setattr(ds_module, "get_compression_service", raise_error)

    saver = ds_module.DataSaver(
        base_output_dir=tmp_path,
        compression_threshold_mb=0.0001,
        enable_background_operations=False,
        flush_interval=1,
    )

    assert not saver._compression_available

    for _ in range(20):
        saver.save(create_reading())

    saver.flush_all()

    compressed_dir = tmp_path / "raw" / "compressed"
    assert not list(compressed_dir.glob("*.csv.gz")), "no compression should occur"
    file_path = tmp_path / "raw" / "s1.csv"
    assert file_path.exists(), "csv should remain when compression unavailable"
    saver.close()


def test_data_saver_background_tasks(tmp_path, monkeypatch):
    dummy = DummyCompressionService()
    monkeypatch.setattr(ds_module, "get_compression_service", lambda: dummy)

    def fast_start(self):
        def worker():
            time.sleep(0.05)
            self._perform_maintenance()

        return self._pool.submit_task(worker, task_id="test_maintenance")

    monkeypatch.setattr(ds_module.DataSaver, "_start_maintenance_thread", fast_start)

    saver = ds_module.DataSaver(
        base_output_dir=tmp_path,
        compression_threshold_mb=0.0001,
        max_file_age_hours=0,
        enable_background_operations=True,
        flush_interval=1,
    )

    old_file = saver.raw_dir / "old.csv"
    old_file.write_text("stale")
    os.utime(old_file, (time.time() - 3600, time.time() - 3600))

    for _ in range(20):
        saver.save(create_reading())

    saver.flush_all()
    time.sleep(0.3)

    compressed_dir = saver.raw_dir / "compressed"
    compressed_files = list(compressed_dir.glob("*.csv.gz"))
    rotated_files = list(compressed_dir.glob("old*.csv"))

    assert compressed_files, "expected compressed file"
    assert rotated_files, "expected rotated file"
    assert not saver._tasks, "background tasks should complete"
    saver.close()


def test_data_saver_thread_safety(tmp_path):
    saver = ds_module.DataSaver(
        base_output_dir=tmp_path,
        enable_background_operations=False,
        flush_interval=1,
    )

    def writer():
        for _ in range(50):
            saver.save(create_reading())

    threads = [threading.Thread(target=writer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    saver.flush_all()
    file_path = tmp_path / "raw" / "s1.csv"
    lines = file_path.read_text().splitlines()
    assert len(lines) == 1 + 4 * 50
    saver.close()


def test_data_saver_sanitizes_id(tmp_path):
    saver = ds_module.DataSaver(
        base_output_dir=tmp_path,
        enable_background_operations=False,
        flush_interval=1,
    )

    unsafe_id = "../bad/id"
    reading = create_reading(unsafe_id)
    saver.save(reading)
    saver.flush_all()

    safe_name = ds_module.sanitize_id(unsafe_id) + ".csv"
    assert (tmp_path / "raw" / safe_name).exists()
    saver.close()
