import json
from cvd.utils.config_service import ConfigurationService


def create_service(tmp_path, cfg):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


def test_load_converts_dict_format(tmp_path):
    cfg = {
        "sensors": {
            "sen1": {
                "name": "s1",
                "type": "temperature",
                "interface": "usb",
                "source": "dev",
                "enabled": True,
            }
        }
    }
    svc = create_service(tmp_path, cfg)
    sensors = svc.get_section("sensors")
    assert isinstance(sensors, list)
    assert sensors[0]["sen1"]["name"] == "s1"


def test_add_update_remove_sensor(tmp_path):
    svc = create_service(tmp_path, {"sensors": []})
    svc.add_sensor_config(
        {
            "sensor_id": "sen1",
            "name": "s1",
            "type": "temperature",
            "interface": "usb",
            "source": "dev",
            "enabled": True,
        }
    )
    assert any(sid == "sen1" for sid, _ in svc.get_sensor_configs())

    assert svc.update_sensor_config("sen1", {"poll_interval_ms": 200}) is True
    cfg = svc.get_sensor_configs()[0][1]
    assert cfg["poll_interval_ms"] == 200

    assert svc.remove_sensor_config("sen1") is True
    assert svc.get_sensor_configs() == []

