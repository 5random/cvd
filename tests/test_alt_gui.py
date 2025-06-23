"""Tests for the alternative GUI (``alt_application.py``) using the NiceGUI
testing framework.

These tests use the NiceGUI user plugin to exercise various GUI flows of the
``SimpleGUIApplication``.
"""

import pytest
from typing import Dict, Any
from collections import deque
import types
from unittest.mock import Mock, AsyncMock

from nicegui import ui
from nicegui.testing import User
from cvd.gui.alt_application import SimpleGUIApplication
from cvd.gui.alt_gui_elements.motion_detection_element import MotionStatusSection
from cvd.utils.config_service import ConfigurationService
from cvd.utils.email_alert_service import EmailAlertService

# Plugin for the NiceGUI testing framework
pytest_plugins = ["nicegui.testing.user_plugin"]


class MockEmailAlertService(EmailAlertService):
    def __init__(self, config_service):
        super().__init__(config_service)
        self._config_service = config_service
        self.enabled = False
        self.recipient = "test@example.com"
        self.smtp_host = "localhost"
        self.smtp_port = 25
        self.smtp_user = None
        self.smtp_password = None
        self.smtp_use_ssl = False
        self.critical_timeout = 60
        self._history = deque(maxlen=100)

    async def send_test_alert(self, message: str) -> bool:
        # Always return True to simulate a successful alert send in tests,
        # as we do not want to send real emails during testing.
        return True

    def get_status(self) -> Dict[str, Any]:
        # Return dynamic values based on the mock's current state
        return {
            "enabled": getattr(self, "enabled", False),
            "last_check": getattr(self, "last_check", None),
            "recipient": getattr(self, "recipient", "test@example.com"),
            "smtp_host": getattr(self, "smtp_host", "localhost"),
            "smtp_port": getattr(self, "smtp_port", 25),
            "smtp_user": getattr(self, "smtp_user", None),
            "smtp_password": getattr(self, "smtp_password", None),
            "smtp_use_ssl": getattr(self, "smtp_use_ssl", False),
            "critical_timeout": getattr(self, "critical_timeout", 60),
            "history": getattr(self, "_history", []),
        }


class MockControllerManager:
    """Mock Controller Manager for tests"""

    def __init__(self):
        self._controllers = {}

    def get_controller(self, controller_id: str):
        return self._controllers.get(controller_id)

    def add_mock_controller(self, controller_id: str, controller):
        self._controllers[controller_id] = controller


class MockExperimentManager:
    """Mock Experiment Manager for tests"""

    def __init__(
        self,
        config_service=None,
        sensor_manager=None,
        controller_manager=None,
        auto_install_signal_handlers=True,
    ):
        self.config_service = config_service
        self.sensor_manager = sensor_manager
        self.controller_manager = controller_manager

    def list_experiments(self):
        return ["exp_001", "exp_002"]

    def get_experiment_config(self, exp_id: str):
        return {"name": f"Test Experiment {exp_id}", "duration": 60}


@pytest.fixture
def mock_config_service(tmp_path):
    """Create a mock ``ConfigurationService``"""
    config_path = tmp_path / "config.json"
    default_path = tmp_path / "default_config.json"

    config_path.write_text("{}")
    default_path.write_text("{}")

    config_service = ConfigurationService(config_path, default_path)
    # Mock some methods
    config_service.get = Mock(
        side_effect=lambda key, type_=str, default=None: {
            "webapp.fps_cap": 30,
            "ui.title": "CVD Tracker Test",
        }.get(key, default)
    )

    return config_service


@pytest.fixture
def mock_controller_manager():
    """Create a mock ``ControllerManager``"""
    return MockControllerManager()


@pytest.fixture
def mock_experiment_manager(mock_config_service, mock_controller_manager):
    """Create a mock ``ExperimentManager``"""
    return MockExperimentManager(
        config_service=mock_config_service, controller_manager=mock_controller_manager
    )


@pytest.fixture
def simple_gui_app(mock_controller_manager, mock_config_service, tmp_path):
    """Create a ``SimpleGUIApplication`` instance for tests"""
    # Mock external dependencies
    import cvd.controllers.controller_manager as cm_module
    import cvd.experiment_manager as em_module

    # Patch the module-level functions to return our mocks
    original_create_manager = getattr(cm_module, "create_cvd_controller_manager", None)
    original_set_experiment_manager = getattr(em_module, "set_experiment_manager", None)

    cm_module.create_cvd_controller_manager = Mock(return_value=mock_controller_manager)
    em_module.set_experiment_manager = Mock()

    app = SimpleGUIApplication(
        controller_manager=mock_controller_manager,
        config_dir=tmp_path,
        email_alert_service_cls=MockEmailAlertService,
    )

    # Restore original functions
    if original_create_manager:
        cm_module.create_cvd_controller_manager = original_create_manager
    if original_set_experiment_manager:
        em_module.set_experiment_manager = original_set_experiment_manager

    return app


class TestSimpleGUIApplicationBasics:
    """Tests for basic functionality of ``SimpleGUIApplication``"""

    async def test_application_initialization(self, simple_gui_app):
        """Test: application is correctly initialized"""
        assert simple_gui_app is not None
        assert simple_gui_app.camera_active is False
        assert simple_gui_app.motion_detected is False
        assert simple_gui_app.experiment_running is False
        assert simple_gui_app.alerts_enabled is False

    async def test_settings_initialization(self, simple_gui_app):
        """Test: default settings are correctly set"""
        settings = simple_gui_app.settings
        assert settings["sensitivity"] == 50
        assert settings["fps"] == 30
        assert settings["resolution"] == "640x480 (30fps)"
        assert settings["rotation"] == 0
        assert settings["roi_enabled"] is False
        assert settings["duration"] == 60
        assert settings["record_video"] is True


class TestSimpleGUIApplicationUI:
    """Tests for the ``SimpleGUIApplication`` user interface"""

    async def test_main_page_loads(self, user: User, simple_gui_app):
        """Test: main page loads and shows expected content"""

        # Setup the page
        @ui.page("/")
        def main_page():
            simple_gui_app.create_main_layout()

        await user.open("/")
        await user.should_see("CVD Tracker - Simple Monitor")

    async def test_header_elements_present(self, user: User, simple_gui_app):
        """Test: header elements are present"""

        @ui.page("/")
        def main_page():
            simple_gui_app.create_header()

        await user.open("/")
        await user.should_see("CVD Tracker - Simple Monitor")
        # Check for status icons (they should be present as HTML elements)
        # Note: Icons might not have visible text, so we test for the page structure

    async def test_dark_mode_toggle(self, user: User, simple_gui_app):
        """Test: dark mode toggle works"""

        @ui.page("/")
        def main_page():
            simple_gui_app.create_header()
            # Add a button to trigger dark mode for testing
            ui.button("Toggle Dark Mode", on_click=simple_gui_app.toggle_dark_mode)

        await user.open("/")

        # Initial state
        initial_dark_mode = simple_gui_app.dark_mode.value

        # Click toggle button
        user.find("Toggle Dark Mode").click()

        # Verify state changed
        assert simple_gui_app.dark_mode.value != initial_dark_mode


class TestSimpleGUIApplicationCameraFunctionality:
    """Tests for camera functionality"""

    async def test_camera_status_update(self, user: User, simple_gui_app):
        """Test: camera status updates correctly"""

        @ui.page("/")
        def main_page():
            simple_gui_app.create_header()

        await user.open("/")

        # Test camera status update
        simple_gui_app.update_camera_status(True)
        assert simple_gui_app.camera_active is True

        simple_gui_app.update_camera_status(False)
        assert simple_gui_app.camera_active is False

    def test_update_camera_status_without_start_button(self, simple_gui_app):
        """update_camera_status should work if start_camera_btn is missing"""

        class DummyVideo:
            def __init__(self):
                self.source = None

            def set_source(self, src):
                self.source = src

        ws = types.SimpleNamespace(video_element=DummyVideo(), camera_active=False)
        simple_gui_app.webcam_stream = ws

        simple_gui_app.update_camera_status(True)
        assert ws.video_element.source == "/video_feed"
        assert ws.camera_active is True

        simple_gui_app.update_camera_status(False)
        assert ws.video_element.source == ""
        assert ws.camera_active is False

    async def test_motion_header_icon_updates(self, user: User, simple_gui_app):
        """Header motion icon should change on motion events"""

        @ui.page("/")
        def main_page():
            simple_gui_app.create_header()

        await user.open("/")

        assert "text-gray-400" in simple_gui_app.motion_status_icon.classes
        assert simple_gui_app.motion_status_icon.name == "motion_photos_off"

        simple_gui_app.update_motion_status(True)
        assert simple_gui_app.motion_detected is True
        assert simple_gui_app.motion_status_icon.name == "motion_photos_on"
        assert "text-orange-300" in simple_gui_app.motion_status_icon.classes

        simple_gui_app.update_motion_status(False)
        assert simple_gui_app.motion_detected is False
        assert simple_gui_app.motion_status_icon.name == "motion_photos_off"
        assert "text-gray-400" in simple_gui_app.motion_status_icon.classes

    def test_motion_status_cleared_when_no_result(self, simple_gui_app, monkeypatch):
        """_refresh_status should reset motion indicators when no result is returned"""

        class DummyElem:
            def __init__(self):
                self.name = ""
                self.text = ""

            def classes(self, **kwargs):
                pass

        # prepare header icon
        simple_gui_app.motion_status_icon = DummyElem()
        simple_gui_app.motion_detected = True

        section = MotionStatusSection.__new__(MotionStatusSection)
        section.motion_icon = DummyElem()
        section.motion_label = DummyElem()
        section.motion_percentage = DummyElem()
        section.confidence_label = DummyElem()
        section.last_motion_label = DummyElem()
        section.detection_count_label = DummyElem()
        section.motion_detected = True
        section._update_callback = simple_gui_app.update_motion_status

        monkeypatch.setattr(section, "_get_result", lambda: None)

        section._refresh_status()

        assert section.motion_detected is False
        assert section.motion_icon.name == "motion_photos_off"
        assert section.motion_label.text == "No Motion Detected"
        assert simple_gui_app.motion_status_icon.name == "motion_photos_off"

    async def test_camera_settings_update(self, simple_gui_app):
        """Test: camera settings are updated correctly"""
        # Test sensitivity update
        simple_gui_app.update_sensitivity(75)
        assert simple_gui_app.settings["sensitivity"] == 75

        # Test FPS update
        simple_gui_app.update_fps(25)
        assert simple_gui_app.settings["fps"] == 25

        # Test resolution update
        simple_gui_app.update_resolution("1280x720 (30fps)")
        assert simple_gui_app.settings["resolution"] == "1280x720 (30fps)"

        # Test rotation update
        simple_gui_app.update_rotation(90)
        assert simple_gui_app.settings["rotation"] == 90


class TestSimpleGUIApplicationExperimentManagement:
    """Tests for experiment management"""

    async def test_experiment_section_creation(self, user: User, simple_gui_app):
        """Test: experiment section is created correctly"""

        @ui.page("/")
        def main_page():
            simple_gui_app.create_main_layout()

        await user.open("/")
        # Verify that experiment elements are present
        # Note: Specific content depends on ExperimentManagementSection implementation

    async def test_experiment_settings_default(self, simple_gui_app):
        """Test: default experiment settings are correct"""
        settings = simple_gui_app.settings
        assert "experiment_name" in settings
        assert settings["duration"] == 60
        assert settings["record_video"] is True
        assert settings["record_motion_data"] is True
        assert settings["record_timestamps"] is True


class TestSimpleGUIApplicationAlertSystem:
    """Tests for the alert system"""

    async def test_alert_status_update(self, simple_gui_app):
        """Test: alert status updates correctly"""
        # Initially alerts should be disabled
        assert simple_gui_app.alerts_enabled is False

        # Test alert configurations exist
        assert simple_gui_app.alert_configurations is not None
        assert simple_gui_app.alert_display is not None

    async def test_alert_configuration_loading(self, simple_gui_app):
        """Test: alert configurations are loaded"""
        # Should have either loaded configs or demo configs
        assert len(simple_gui_app.alert_configurations) > 0


class TestSimpleGUIApplicationNavigation:
    """Tests for navigation and page actions"""

    async def test_fullscreen_toggle(self, user: User, simple_gui_app):
        """Test: fullscreen toggle"""

        @ui.page("/")
        def main_page():
            ui.button("Toggle Fullscreen", on_click=simple_gui_app.toggle_fullscreen)

        await user.open("/")
        # This will trigger JavaScript, but we can't easily test the actual fullscreen state
        # We just verify the method can be called without errors
        user.find("Toggle Fullscreen").click()

    async def test_page_reload(self, user: User, simple_gui_app):
        """Test: page reload"""

        @ui.page("/")
        def main_page():
            ui.button("Reload Page", on_click=simple_gui_app.reload_page)

        await user.open("/")
        # Similar to fullscreen, we test that the method can be called
        user.find("Reload Page").click()


class TestSimpleGUIApplicationIntegration:
    """Integration tests for the entire application"""

    async def test_complete_layout_creation(self, user: User, simple_gui_app):
        """Test: full layout is created without errors"""

        @ui.page("/")
        def main_page():
            try:
                simple_gui_app.create_main_layout()
            except Exception as e:
                ui.label(f"Error: {str(e)}")
                raise

        await user.open("/")
        await user.should_see("CVD Tracker - Simple Monitor")

    async def test_time_display_updates(self, user: User, simple_gui_app):
        """Test: time display updates"""

        @ui.page("/")
        def main_page():
            simple_gui_app.create_header()
            # Manually trigger time update for testing
            simple_gui_app.update_time()

        await user.open("/")
        # The time should be displayed (format: HH:MM:SS)
        # We can't easily test the exact time, but we can verify the method works
        assert simple_gui_app.time_label.text != ""


class TestSimpleGUIApplicationErrorHandling:
    """Tests for error handling"""

    async def test_missing_controller_handling(self, simple_gui_app):
        """Test: handling missing controllers"""
        # Test accessing non-existent controllers
        assert simple_gui_app.camera_controller is None
        assert simple_gui_app.motion_controller is None

        # Methods should handle missing controllers gracefully
        simple_gui_app.update_sensitivity(50)  # Should not crash
        simple_gui_app.update_fps(30)  # Should not crash

    async def test_invalid_settings_handling(self, simple_gui_app):
        """Test: handling invalid settings"""
        # Test with invalid rotation values
        simple_gui_app.update_rotation(45)  # Should be normalized to valid value
        assert simple_gui_app.settings["rotation"] in [0, 90, 180, 270]

        simple_gui_app.update_rotation(360)  # Should be normalized
        assert simple_gui_app.settings["rotation"] == 0


# Helper functions for advanced tests
def create_mock_camera_controller():
    """Create a mock camera controller"""
    controller = Mock()
    controller.start = AsyncMock(return_value=True)
    controller.stop = AsyncMock()
    controller.cleanup = AsyncMock()
    controller.fps = 30
    controller.width = 640
    controller.height = 480
    return controller


def create_mock_motion_controller():
    """Create a mock motion detection controller"""
    controller = Mock()
    controller.start = AsyncMock(return_value=True)
    controller.stop = AsyncMock()
    controller.motion_threshold_percentage = 50
    controller.fps = 30
    controller.width = 640
    controller.height = 480
    return controller


class TestSimpleGUIApplicationWithMockControllers:
    """Tests with mock controllers for extended functionality"""

    async def test_camera_toggle_with_controller(self, simple_gui_app):
        """Test: camera toggle with mock controller"""
        # Add mock camera controller
        mock_camera = create_mock_camera_controller()
        simple_gui_app.controller_manager.add_mock_controller(
            "camera_capture", mock_camera
        )
        simple_gui_app.camera_controller = mock_camera

        # Test toggle on
        await simple_gui_app.toggle_camera()

        # Verify start was called and state updated
        mock_camera.start.assert_called_once()
        assert simple_gui_app.camera_active is True

    async def test_camera_toggle_with_motion_controller(self, simple_gui_app):
        """Camera and motion controllers should start and stop together"""

        mock_camera = create_mock_camera_controller()
        mock_motion = create_mock_motion_controller()
        simple_gui_app.controller_manager.add_mock_controller("camera_capture", mock_camera)
        simple_gui_app.controller_manager.add_mock_controller("motion_detection", mock_motion)
        simple_gui_app.camera_controller = mock_camera
        simple_gui_app.motion_controller = mock_motion

        # Start streaming
        await simple_gui_app.toggle_camera()

        mock_camera.start.assert_called_once()
        mock_motion.start.assert_called_once()
        assert simple_gui_app.camera_active is True

        # Stop streaming
        await simple_gui_app.toggle_camera()

        mock_camera.stop.assert_called_once()
        mock_motion.stop.assert_called_once()
        assert simple_gui_app.camera_active is False

    async def test_camera_toggle_start_failure(self, simple_gui_app, monkeypatch):
        """Camera remains inactive and user is notified if start fails"""

        mock_camera = create_mock_camera_controller()
        mock_camera.start = AsyncMock(return_value=False)
        simple_gui_app.controller_manager.add_mock_controller(
            "camera_capture", mock_camera
        )
        simple_gui_app.camera_controller = mock_camera

        notifications = []

        def notifier(msg, **kw):
            notifications.append(msg)

        monkeypatch.setattr("cvd.utils.ui_helpers.notify_later", notifier)
        monkeypatch.setattr("cvd.gui.alt_application.notify_later", notifier)

        await simple_gui_app.toggle_camera()

        assert simple_gui_app.camera_active is False
        assert notifications
        assert "Failed to start camera" in notifications[0]

    async def test_camera_toggle_stop_failure(self, simple_gui_app, monkeypatch):
        """Camera stays active and user is notified if stop fails"""

        mock_camera = create_mock_camera_controller()
        simple_gui_app.controller_manager.add_mock_controller(
            "camera_capture", mock_camera
        )
        simple_gui_app.camera_controller = mock_camera

        await simple_gui_app.toggle_camera()
        assert simple_gui_app.camera_active is True

        mock_camera.stop = AsyncMock(side_effect=RuntimeError("boom"))
        notifications = []

        def notifier(msg, **kw):
            notifications.append(msg)

        monkeypatch.setattr("cvd.utils.ui_helpers.notify_later", notifier)
        monkeypatch.setattr("cvd.gui.alt_application.notify_later", notifier)

        await simple_gui_app.toggle_camera()

        assert simple_gui_app.camera_active is True
        assert notifications
        assert "Failed to stop camera" in notifications[0]

    async def test_motion_detection_settings_with_controller(self, simple_gui_app):
        """Test: motion detection settings with mock controller"""
        # Add mock motion controller
        mock_motion = create_mock_motion_controller()
        simple_gui_app.controller_manager.add_mock_controller(
            "motion_detection", mock_motion
        )
        simple_gui_app.motion_controller = mock_motion

        # Test sensitivity update
        simple_gui_app.update_sensitivity(80)

        # Verify controller was updated
        assert mock_motion.motion_threshold_percentage == 80

        # Test FPS update
        simple_gui_app.update_fps(60)
        assert mock_motion.fps == 60


# Additional test fixtures for special scenarios
@pytest.fixture
def gui_app_with_mocked_dependencies(tmp_path):
    """GUI app with all important dependencies mocked"""
    # Additional specific mock setups for more complex tests can be added here
    pass


# Performance and load tests (optional)
class TestSimpleGUIApplicationPerformance:
    """Performance tests (optional, for larger test suites)."""

    # Uncomment the following decorator to mark this test as slow
    # @pytest.mark.slow
    async def test_rapid_setting_updates(self, simple_gui_app):
        """Test: rapid consecutive setting changes"""
        # Test rapid updates don't cause issues
        # FPS will be in the range 20-59 (inclusive) due to 20 + (i % 40)
        for i in range(100):
            simple_gui_app.update_sensitivity(i % 100)
            simple_gui_app.update_fps(20 + (i % 40))
            # Optional: Add intermediate assertions for debugging
            assert 0 <= simple_gui_app.settings["sensitivity"] <= 100
            assert simple_gui_app.settings["fps"] > 0

        # App should still be in consistent state
        assert 0 <= simple_gui_app.settings["sensitivity"] <= 100
        assert simple_gui_app.settings["fps"] > 0
        assert simple_gui_app.settings["fps"] > 0
