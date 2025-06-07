import os
from pathlib import Path
import time

import pytest

from src.utils.data_utils import data_saver as ds_module
from src.data_handler.interface.sensor_interface import SensorReading, SensorStatus


class DummyCompressionService:
    def __init__(self):
        self.calls = []

    def compress_file(self, src: str, dst: str):
        # simply copy the input to the destination
        with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
            fdst.write(fsrc.read())
        self.calls.append((src, dst))
        return Path(dst)


def create_reading(sensor_id: str = "s1") -> SensorReading:
    return SensorReading(sensor_id, 1.0, time.time(), SensorStatus.OK)


def test_data_saver_sync_compression(tmp_path, monkeypatch):
    dummy = DummyCompressionService()
    monkeypatch.setattr(ds_module, "get_compression_service", lambda: dummy)

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
