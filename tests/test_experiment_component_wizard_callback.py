import json

from program.src.utils.config_utils.config_service import ConfigurationService
import program.src.gui.gui_tab_components.gui_tab_experiment_component as exp_mod


def create_service(tmp_path, cfg=None):
    cfg = cfg or {}
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default.json"
    config_path.write_text(json.dumps(cfg))
    default_path.write_text("{}")
    return ConfigurationService(config_path, default_path)


class DummyExpManager:
    pass


class DummyDisplay:
    def __init__(self):
        self.updated = False

    def update(self, data):
        self.updated = True

    def cleanup(self):
        pass

    def render(self):
        pass


class DummyHistory:
    def __init__(self):
        self.updated = False

    def update(self, data):
        self.updated = True

    def cleanup(self):
        pass

    def render(self):
        pass


def test_wizard_close_triggers_refresh(monkeypatch, tmp_path):
    svc = create_service(tmp_path)

    # ensure experiment manager is provided
    monkeypatch.setattr(exp_mod, "get_experiment_manager", lambda: DummyExpManager())

    component = exp_mod.ExperimentComponent(
        exp_mod.ComponentConfig("exp"), svc, None, None
    )
    component.current_experiment_display = DummyDisplay()
    component.history_table = DummyHistory()

    captured = {}

    class DummyWizard:
        def __init__(self, *a, **kw):
            captured["callback"] = kw.get("on_close")

        def show_dialog(self):
            pass

    monkeypatch.setattr(exp_mod, "ExperimentSetupWizardComponent", DummyWizard)

    component._show_new_experiment_dialog()

    callback = captured.get("callback")
    assert callback is not None

    # simulate dialog close
    callback()

    assert component.current_experiment_display.updated
    assert component.history_table.updated
