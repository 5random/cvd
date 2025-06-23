import os
import gzip
from pathlib import Path
import time
import zipfile

import pytest

from cvd.utils.data_utils.data_manager import DataManager
from cvd.utils.data_utils.maintenance import MaintenanceManager
from cvd.utils.data_utils.indexing import FileStatus


class DummyCompressionSettings:
    def __init__(self):
        self.preserve_original = False


class DummyCompressionService:

    def __init__(self):

        class Settings:
            preserve_original = False

        self._compression_settings = DummyCompressionSettings()

    def compress_file(self, src: str, dst: str):
        with open(src, "rb") as f_in, gzip.open(dst, "wb") as f_out:
            f_out.write(f_in.read())

        if not self._compression_settings.preserve_original:
            os.remove(src)

        return Path(dst)


@pytest.fixture
def data_manager(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_WATCHDOG", "0")
    # Ensure configuration service does not override test paths
    import cvd.utils.config_service as cs_module
    cs_module._config_service_instance = None
    monkeypatch.setattr(MaintenanceManager, "start_worker", lambda self: None)
    mgr = DataManager(base_output_dir=tmp_path)
    yield mgr


def test_scan_and_download(tmp_path, data_manager):
    dm = data_manager

    f1 = dm.raw_dir / "sensor1.csv"
    f1.write_text("data")
    f2 = dm.processed_dir / "experiment_1.csv"
    f2.write_text("proc")

    processed = dm.scan_directories()
    assert processed >= 2

    req_id = dm.create_download_package([str(f1.resolve())])

    download = None
    for _ in range(20):
        download = dm.get_download_file(req_id)
        if download:
            break
        time.sleep(0.1)

    assert download and download.exists()
    with zipfile.ZipFile(download) as z:
        assert any(p.endswith("sensor1.csv") for p in z.namelist())


def test_background_maintenance_compression(tmp_path, data_manager):
    dm = data_manager
    dm._compression_service = DummyCompressionService()
    dm._maintenance_service.compression_service = dm._compression_service
    dm._maintenance_service.threshold = 1
    dm._maintenance_service.max_age = 3600

    f = dm.raw_dir / "sensorX.csv"
    f.write_text("0123456789")

    dm.scan_directories()
    assert str(f.resolve()) in dm._index.files

    dm._maintenance_service.compress_inactive_files([dm.raw_dir])
    dm.scan_directories()

    compressed = list((dm.raw_dir / "compressed").glob("*.csv.gz"))
    assert compressed
    assert not f.exists()
    comp_path = compressed[0]
    meta = dm._index.files.get(str(comp_path.resolve()))
    assert meta and meta.status == FileStatus.COMPRESSED


def test_experiment_id_zip(tmp_path, data_manager):
    dm = data_manager

    zip_file = dm.processed_dir / "experiment_5.zip"
    zip_file.write_text("dummy")

    dm.scan_directories()

    meta = dm._index.files.get(str(zip_file.resolve()))
    assert meta and meta.experiment_id == "5"
