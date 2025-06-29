import logging
from pathlib import Path
import zipfile


from cvd.utils.config_service import ConfigurationService, set_config_service
from cvd.utils.data_utils.compression_service import (
    CompressionService,
    set_compression_service,
)
from cvd.utils.data_utils.data_saver import DataSaver
from cvd.utils.data_utils.file_management_service import FileMaintenanceService


def _init_services(
    tmp_path: Path,
) -> tuple[ConfigurationService, CompressionService, DataSaver]:
    cfg_dir = tmp_path
    (cfg_dir / "config.json").write_text("{}")
    (cfg_dir / "default_config.json").write_text("{}")
    config_service = ConfigurationService(
        cfg_dir / "config.json", cfg_dir / "default_config.json"
    )
    set_config_service(config_service)

    compression_service = CompressionService()
    set_compression_service(compression_service)

    data_saver = DataSaver(base_output_dir=tmp_path, enable_background_operations=False)
    return config_service, compression_service, data_saver


def _init_compression_service(tmp_path: Path) -> CompressionService:
    cfg_dir = tmp_path
    (cfg_dir / "config.json").write_text("{}")
    (cfg_dir / "default_config.json").write_text("{}")
    config_service = ConfigurationService(
        cfg_dir / "config.json", cfg_dir / "default_config.json"
    )
    set_config_service(config_service)
    compression_service = CompressionService()
    set_compression_service(compression_service)
    return compression_service


def test_data_saver_compress_sync(tmp_path: Path, caplog):
    _, compression_service, data_saver = _init_services(tmp_path)

    file_path = tmp_path / "raw" / "sample.csv"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("a,b\n1,2\n")

    caplog.set_level(logging.WARNING, logger="cvd_tracker.error")

    # Should not raise FileNotFoundError even though CompressionService removes the file
    result = data_saver._compress_file_sync(file_path)

    assert result is not None and result.exists()
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)

    compressed = list((file_path.parent / "compressed").glob("sample*.csv.gz"))
    assert len(compressed) == 1
    assert not file_path.exists()


def test_file_maintenance_compress(tmp_path: Path, caplog):
    _, compression_service, _ = _init_services(tmp_path)
    service = FileMaintenanceService(
        compression_service, compression_threshold_bytes=0, max_file_age_seconds=0
    )

    file_path = tmp_path / "example.csv"
    file_path.write_text("x,y\n")

    caplog.set_level(logging.WARNING, logger="cvd_tracker.error")
    result = service._compress_file(file_path)

    assert result is not None and result.exists()
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)

    compressed = list((tmp_path / "compressed").glob("example*.csv.gz"))
    assert len(compressed) == 1
    assert not file_path.exists()


def test_is_already_compressed_partial_match(tmp_path: Path):
    _, compression_service, _ = _init_services(tmp_path)

    assert not compression_service._is_already_compressed(Path("uncompressed/file.csv"))


def test_is_already_compressed_dir_name(tmp_path: Path):
    _, compression_service, _ = _init_services(tmp_path)

    assert compression_service._is_already_compressed(Path("data/compressed/file.csv"))


def test_is_already_compressed_extension(tmp_path: Path):
    _, compression_service, _ = _init_services(tmp_path)

    assert compression_service._is_already_compressed(Path("file.csv.gz"))


def test_compression_settings_property(tmp_path: Path):
    _, compression_service, _ = _init_services(tmp_path)

    assert compression_service.compression_settings is getattr(
        compression_service, "_compression_settings"
    )


def test_decompress_zip_prevents_path_traversal(tmp_path: Path):
    compression_service = _init_compression_service(tmp_path)

    archive = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../evil.txt", "bad")

    dest = tmp_path / "out"
    dest.mkdir()

    result = compression_service.decompress_file(archive, dest)

    assert result is None
    assert not (tmp_path / "evil.txt").exists()
    assert not any(dest.iterdir())


def test_decompress_zip_valid(tmp_path: Path):
    compression_service = _init_compression_service(tmp_path)

    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("good.txt", "hello")

    dest = tmp_path / "extract"
    dest.mkdir()

    result = compression_service.decompress_file(archive, dest)

    assert result == dest
    assert (dest / "good.txt").read_text() == "hello"
