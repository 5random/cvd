import json

from src.utils.config_utils.config_service import ConfigurationService
from src.gui.gui_tab_components.gui_tab_dashboard_component import DashboardComponent


def create_service(tmp_path, cfg):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


def test_motion_detection_camera_detection(tmp_path):
    cfg = {
        "controllers": [
            {
                "md1": {
                    "name": "MD",
                    "type": "motion_detection",
                    "parameters": {"cam_id": "cam1"},
                    "show_on_dashboard": True,
                    "enabled": True,
                }
            }
        ]
    }

    service = create_service(tmp_path, cfg)
    dashboard = DashboardComponent(service, None, None)

    assert dashboard._should_show_camera() is True
