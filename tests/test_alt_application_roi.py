import pytest
from src.controllers.roi_utils import clamp_roi, rotate_roi


@pytest.mark.parametrize(
    "roi,width,height,expected",
    [
        ((10, 20, 30, 40), 100, 80, (10, 20, 30, 40)),  # already within bounds
        ((-10, -5, 30, 40), 100, 80, (0, 0, 30, 40)),  # negative coordinates
        ((90, 60, 20, 30), 100, 80, (90, 60, 10, 20)),  # width and height clip
        ((10, 70, 30, 20), 100, 80, (10, 70, 30, 10)),  # height clip only
        ((10, 10, -5, -5), 100, 80, (10, 10, 0, 0)),  # negative size
        ((10, 10, 30, 40), None, 80, (10, 10, 30, 40)),  # width None
        ((10, 10, 30, 40), 100, None, (10, 10, 30, 40)),  # height None
        ((10, 10, 30, 40), None, None, (10, 10, 30, 40)),  # both None
    ],
)
def test_clamp_roi(roi, width, height, expected):
    assert clamp_roi(roi, width, height) == expected


@pytest.mark.parametrize(
    "roi,old_rot,new_rot,width,height,expected",
    [
        ((10, 20, 30, 40), 0, 90, 100, 80, (20, 60, 40, 30)),
        ((10, 20, 30, 40), 90, 0, 100, 80, (40, 10, 40, 30)),
        ((-5, 10, 20, 30), 270, 180, 100, 80, (60, -5, 30, 20)),
        ((0, 10, 10, 10), -90, 450, 100, 80, (70, 80, 10, 10)),
        ((5, 5, 10, 10), 180, 180, 100, 80, (5, 5, 10, 10)),  # no rotation change
    ],
)
def test_rot_roi(roi, old_rot, new_rot, width, height, expected):
    assert rotate_roi(roi, old_rot, new_rot, width, height) == expected


def test_update_rotation_swaps_container_and_roi(tmp_path, monkeypatch):
    from types import SimpleNamespace, ModuleType
    from nicegui import ui
    import sys

    dummy_module = ModuleType("alert_element_new")
    dummy_module.create_compact_alert_widget = lambda *a, **k: None
    dummy_module.create_demo_configurations = lambda *a, **k: []
    dummy_module.create_email_alert_status_display = lambda *a, **k: None
    dummy_module.create_email_alert_wizard = lambda *a, **k: None
    dummy_module.load_alert_configs = lambda *a, **k: []
    dummy_module.save_alert_configs = lambda *a, **k: None
    dummy_module.EmailAlertsSection = None
    dummy_module.EmailAlertStatusDisplay = lambda *a, **k: SimpleNamespace(
        update_callback=None
    )
    sys.modules.setdefault("src.gui.alt_gui_elements.alert_element_new", dummy_module)

    class DummyControllerManager:
        def get_controller(self, cid):
            return None

    from src.gui.alt_application import SimpleGUIApplication
    from src.gui import ui_helpers

    monkeypatch.setattr(ui_helpers, "notify_later", lambda *a, **k: None)

    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "default_config.json").write_text("{}")

    app = SimpleGUIApplication(
        controller_manager=DummyControllerManager(), config_dir=tmp_path
    )

    container = ui.card().style("width: 640px; height: 480px;")
    ws = SimpleNamespace(
        video_container=container,
        roi_x=10,
        roi_y=20,
        roi_width=30,
        roi_height=40,
    )

    def swap_dims():
        style = getattr(container, "_style", {})
        w = style.get("width")
        h = style.get("height")
        if w and h:
            container.style(f"width: {h}; height: {w};")

    ws.swap_video_container_dimensions = swap_dims
    app.webcam_stream = ws
    app.settings["roi_enabled"] = True
    app.settings.update({"roi_x": 10, "roi_y": 20, "roi_width": 30, "roi_height": 40})

    app.update_rotation(90)

    assert ws.video_container._style["width"] == "480px"
    assert ws.video_container._style["height"] == "640px"
    expected = rotate_roi((10, 20, 30, 40), 0, 90, 640, 480)
    expected = clamp_roi(expected, 480, 640)
    assert (ws.roi_x, ws.roi_y, ws.roi_width, ws.roi_height) == expected
