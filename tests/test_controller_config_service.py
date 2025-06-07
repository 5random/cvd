import json
from src.utils.config_utils.config_service import ConfigurationService


def create_service(tmp_path, cfg):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


def test_update_controller_parameters_list(tmp_path):
    cfg = {
        "controllers": [
            {"con1": {"name": "c", "type": "motion_detection", "parameters": {"a": 1}, "enabled": True}}
        ]
    }
    svc = create_service(tmp_path, cfg)
    assert svc.update_controller_parameters("con1", {"a": 2, "b": 3}) is True
    params = svc.get_controller_parameters("con1")
    assert params == {"a": 2, "b": 3}


def test_update_controller_parameters_dict(tmp_path):
    cfg = {
        "controllers": {
            "con1": {"name": "c", "type": "motion_detection", "parameters": {"x": "y"}, "enabled": True}
        }
    }
    svc = create_service(tmp_path, cfg)
    assert svc.update_controller_parameters("con1", {"z": 1}) is True
    params = svc.get_controller_parameters("con1")
    assert params == {"x": "y", "z": 1}

