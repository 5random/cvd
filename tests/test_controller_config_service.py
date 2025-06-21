import json
from program.src.utils.config_utils.config_service import ConfigurationService


def create_service(tmp_path, cfg):
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


def test_update_controller_parameters_list(tmp_path):
    cfg = {
        "controllers": [
            {
                "con1": {
                    "name": "c",
                    "type": "motion_detection",
                    "parameters": {"a": 1},
                    "enabled": True,
                }
            }
        ]
    }
    svc = create_service(tmp_path, cfg)
    assert svc.update_controller_parameters("con1", {"a": 2, "b": 3}) is True
    params = svc.get_controller_parameters("con1")
    assert params == {"a": 2, "b": 3}


def test_update_controller_parameters_dict(tmp_path):
    cfg = {
        "controllers": {
            "con1": {
                "name": "c",
                "type": "motion_detection",
                "parameters": {"x": "y"},
                "enabled": True,
            }
        }
    }
    svc = create_service(tmp_path, cfg)
    assert svc.update_controller_parameters("con1", {"z": 1}) is True
    params = svc.get_controller_parameters("con1")
    assert params == {"x": "y", "z": 1}


def test_helper_option_lists(tmp_path):
    cfg = {
        "webcams": [{"cam1": {"name": "w1", "device_index": 0}}],
        "controllers": [],
    }
    svc = create_service(tmp_path, cfg)

    assert svc.get_webcam_ids() == ["cam1"]
    assert "motion_detection" in svc.get_controller_type_options()


def test_wizard_parameter_defaults(tmp_path):
    """Parameters are prefilled from templates for each controller type."""
    from program.src.gui.gui_elements.gui_controller_setup_wizard_element import (
        ControllerSetupWizardComponent,
        _PARAM_TEMPLATES,
    )

    class Dummy:
        pass

    svc = create_service(tmp_path, {"controllers": []})
    wizard = ControllerSetupWizardComponent(svc, Dummy(), Dummy())

    for ctype in wizard._controller_types:
        template = _PARAM_TEMPLATES[ctype]
        wizard._wizard_data["type"] = ctype
        wizard._update_controller_defaults()
        expected = {k: v["default"] for k, v in template.items()}
        if ctype == "motion_detection":
            expected.update(
                {"roi_x": 0, "roi_y": 0, "roi_width": 0, "roi_height": 0}
            )
        assert wizard._wizard_data["parameters"] == expected
