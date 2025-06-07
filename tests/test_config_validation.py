import pytest
from src.utils.config_utils.config_service import ConfigurationService, ValidationError

@pytest.mark.asyncio
async def test_validate_sensor_config_missing_field(tmp_path):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text("{}")
    default_path.write_text("{}")

    service = ConfigurationService(config_path, default_path)

    invalid_cfg = {
        "sensor_id": "sen1",
        "type": "temperature",
        "interface": "serial",
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
        "enabled": True,
        "channel": 1
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
        "rotation": 45
    }

    with pytest.raises(ValidationError):
        service._validate_webcam_config(invalid_cfg)
