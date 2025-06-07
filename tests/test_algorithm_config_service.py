import json
from src.utils.config_utils.config_service import ConfigurationService

def create_service(tmp_path, cfg):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


def test_update_and_remove_algorithm_list(tmp_path):
    cfg = {
        "algorithms": [
            {"alg1": {"name": "a", "type": "smoothing", "enabled": True}}
        ]
    }
    svc = create_service(tmp_path, cfg)
    assert svc.update_algorithm_config("alg1", {"enabled": False}) is True
    alg = svc.get_algorithm_config("alg1")
    assert alg and alg["enabled"] is False
    assert svc.remove_algorithm_config("alg1") is True
    assert svc.get_algorithm_config("alg1") is None


def test_update_and_remove_algorithm_dict(tmp_path):
    cfg = {
        "algorithms": {
            "alg1": {"name": "a", "type": "smoothing", "enabled": True}
        }
    }
    svc = create_service(tmp_path, cfg)
    assert svc.update_algorithm_config("alg1", {"enabled": False}) is True
    alg = svc.get_algorithm_config("alg1")
    assert alg and alg["enabled"] is False
    assert svc.remove_algorithm_config("alg1") is True
    assert svc.get_algorithm_config("alg1") is None
