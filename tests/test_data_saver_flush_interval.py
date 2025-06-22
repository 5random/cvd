from src.utils.container import ApplicationContainer


def test_data_saver_flush_interval_from_config(tmp_path):
    config_dir = tmp_path
    cfg = {
        "data_storage": {
            "storage_paths": {"base": str(tmp_path / "data")},
            "flush_interval": 3,
        }
    }
    (config_dir / "config.json").write_text(__import__("json").dumps(cfg))
    (config_dir / "default_config.json").write_text("{}")

    container = ApplicationContainer.create(config_dir)
    try:
        assert container.data_saver.flush_interval == 3
    finally:
        container.shutdown_sync()


def test_data_saver_flush_interval_defaults_to_one(tmp_path):
    config_dir = tmp_path
    cfg = {
        "data_storage": {
            "storage_paths": {"base": str(tmp_path / "data")},
            "flush_interval": 0,
        }
    }
    (config_dir / "config.json").write_text(__import__("json").dumps(cfg))
    (config_dir / "default_config.json").write_text("{}")

    container = ApplicationContainer.create(config_dir)
    try:
        assert container.data_saver.flush_interval == 1
    finally:
        container.shutdown_sync()
