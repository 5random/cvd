import logging
import pytest
from src.utils.config_utils.config_service import ConfigurationService, ValidationError


@pytest.mark.asyncio
async def test_validate_sensor_config_missing_source(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    invalid_cfg = {
        "sensor_id": "sen1",
        "name": "t1",
        "type": "temperature",
        "interface": "usb",
        "enabled": True,
    }

    with pytest.raises(ValidationError):
        service._validate_sensor_config(invalid_cfg)


@pytest.mark.asyncio
async def test_validate_sensor_interface_requirements(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    invalid_cfg = {
        "sensor_id": "sen1",
        "name": "t1",
        "type": "temperature",
        "interface": "serial",
        "source": "arduino_tc_board",
        "enabled": True,
        "channel": 1,
    }

    with pytest.raises(ValidationError):
        service._validate_sensor_config(invalid_cfg)


@pytest.mark.asyncio
async def test_validate_webcam_invalid_rotation(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    invalid_cfg = {
        "webcam_id": "cam1",
        "name": "cam1",
        "device_index": 0,
        "rotation": 45,
    }

    with pytest.raises(ValidationError):
        service._validate_webcam_config(invalid_cfg)


@pytest.mark.asyncio
async def test_sensor_invalid_poll_interval_type(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    invalid_cfg = {
        "sensor_id": "sen1",
        "name": "t1",
        "type": "temperature",
        "interface": "usb",
        "source": "dev",
        "enabled": True,
        "poll_interval_ms": "100",  # invalid type
    }

    with pytest.raises(ValidationError):
        service._validate_sensor_config(invalid_cfg)


@pytest.mark.asyncio
async def test_sensor_optional_fields_missing(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    valid_cfg = {
        "sensor_id": "sen1",
        "name": "t1",
        "type": "temperature",
        "interface": "usb",
        "source": "dev",
        "enabled": True,
    }

    service._validate_sensor_config(valid_cfg)


@pytest.mark.asyncio
async def test_sensor_unexpected_key_warns(tmp_path, caplog):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    cfg = {
        "sensor_id": "sen1",
        "name": "t1",
        "type": "temperature",
        "interface": "usb",
        "source": "dev",
        "enabled": True,
        "unexpected": 1,
    }

    caplog.set_level(logging.WARNING)
    service._validate_sensor_config(cfg)
    assert any("Unknown field" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_sensor_baudrate_timeout_known(tmp_path, caplog):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    cfg = {
        "sensor_id": "sen1",
        "name": "t1",
        "type": "temperature",
        "interface": "serial",
        "source": "dev",
        "enabled": True,
        "port": "COM1",
        "channel": 1,
        "baudrate": 9600,
        "timeout": 2.0,
    }

    caplog.set_level(logging.WARNING)
    service._validate_sensor_config(cfg)
    assert not any("Unknown field" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_controller_invalid_interface_requirements(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    invalid_cfg = {
        "controller_id": "con1",
        "name": "c1",
        "type": "motion_detection",
        "interface": "usb_camera",
        "enabled": True,
    }

    with pytest.raises(ValidationError):
        service._validate_controller_config(invalid_cfg)


@pytest.mark.asyncio
async def test_controller_minimal_valid(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    cfg = {"controller_id": "con1", "name": "c1", "type": "motion_detection", "enabled": True}

    service._validate_controller_config(cfg)


@pytest.mark.asyncio
async def test_controller_unexpected_key_warns(tmp_path, caplog):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    cfg = {
        "controller_id": "con1",
        "name": "c1",
        "type": "motion_detection",
        "enabled": True,
        "foo": "bar",
    }

    caplog.set_level(logging.WARNING)
    service._validate_controller_config(cfg)
    assert any("Unknown field" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_webcam_minimal_valid(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    cfg = {"webcam_id": "cam1", "name": "cam1", "device_index": 0}

    service._validate_webcam_config(cfg)


@pytest.mark.asyncio
async def test_webcam_uvc_unexpected_key(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    invalid_cfg = {
        "webcam_id": "cam1",
        "name": "cam1",
        "device_index": 0,
        "uvc": {"bad": 1},
    }

    with pytest.raises(ValidationError):
        service._validate_webcam_config(invalid_cfg)


@pytest.mark.asyncio
async def test_algorithm_invalid_enabled_type(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    invalid_cfg = {
        "algorithm_id": "alg1",
        "name": "a1",
        "type": "smoothing",
        "enabled": "yes",
    }

    with pytest.raises(ValidationError):
        service._validate_algorithm_config(invalid_cfg)


@pytest.mark.asyncio
async def test_algorithm_optional_fields_missing(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    cfg = {"algorithm_id": "alg1", "name": "a1", "type": "smoothing", "enabled": True}

    service._validate_algorithm_config(cfg)


@pytest.mark.asyncio
async def test_algorithm_unexpected_key_warns(tmp_path, caplog):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    cfg = {
        "algorithm_id": "alg1",
        "name": "a1",
        "type": "smoothing",
        "enabled": True,
        "extra": 1,
    }

    caplog.set_level(logging.WARNING)
    service._validate_algorithm_config(cfg)
    assert any("Unknown field" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_motion_detection_algorithm_enum(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    invalid_cfg = {
        "controller_id": "con1",
        "name": "c1",
        "type": "motion_detection",
        "enabled": True,
        "parameters": {"algorithm": "INVALID"},
    }

    with pytest.raises(ValidationError):
        service._validate_controller_config(invalid_cfg)

    valid_cfg = {
        "controller_id": "con1",
        "name": "c1",
        "type": "motion_detection",
        "enabled": True,
        "parameters": {"algorithm": "MOG2"},
    }

    service._validate_controller_config(valid_cfg)


@pytest.mark.asyncio
async def test_motion_detection_additional_params(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    cfg = {
        "controller_id": "con1",
        "name": "c1",
        "type": "motion_detection",
        "enabled": True,
        "parameters": {
            "algorithm": "KNN",
            "var_threshold": 10,
            "dist2_threshold": 5.0,
            "history": 50,
            "detect_shadows": False,
        },
    }

    service._validate_controller_config(cfg)
