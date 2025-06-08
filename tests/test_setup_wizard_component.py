import json
from src.utils.config_utils.config_service import ConfigurationService
from src.gui.gui_tab_components.gui_setup_wizard_component import SetupWizardComponent

class Dummy:
    pass

def create_service(tmp_path, cfg):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


def test_update_element_refreshes_lists(tmp_path):
    cfg = {
        "sensors": [
            {
                "sen1": {
                    "name": "S1",
                    "type": "temperature",
                    "interface": "serial",
                    "source": "s",
                    "port": "COM1",
                    "channel": 1,
                    "enabled": True,
                }
            }
        ],
        "controllers": [
            {"con1": {"name": "C1", "type": "camera_capture", "enabled": True}}
        ],
    }
    svc = create_service(tmp_path, cfg)
    wizard = SetupWizardComponent(svc, Dummy(), Dummy())
    wizard.render()
    assert len(wizard._sensor_list.default_slot.children) == 1
    assert len(wizard._controller_list.default_slot.children) == 1

    svc.add_sensor_config(
        {
            "sensor_id": "sen2",
            "name": "S2",
            "type": "temperature",
            "interface": "serial",
            "source": "s",
            "port": "COM2",
            "channel": 2,
            "enabled": True,
        }
    )
    svc.add_controller_config(
        {"controller_id": "con2", "name": "C2", "type": "camera_capture", "enabled": True}
    )

    wizard._update_element({})

    assert len(wizard._sensor_list.default_slot.children) == 2
    assert len(wizard._controller_list.default_slot.children) == 2
