"""UI elements for configuring and testing basic email alerts."""

from nicegui import ui


class EmailAlertsSection:
    """Section for managing email alert settings within the GUI."""
    def __init__(self, settings, callbacks=None):
        """Initialize email alerts section with settings"""
        self.experiment_running = False
        self.alerts_enabled = False
        settings = settings or {"email": "user@example.com", "alert_delay": 5}
        self.settings = settings
        self.callbacks = callbacks or {}

        @ui.page("/email_alerts")
        def page():
            """Create the email alerts configuration section"""
            self.create_email_alerts_section()

    def create_email_alerts_section(self):
        """Create email alerts configuration section"""
        with ui.card().classes("cvd-card w-full"):
            ui.label("Email Alerts").classes("text-lg font-bold mb-2")

            # Enable/disable alerts
            self.alerts_enabled_checkbox = ui.checkbox(
                "Enable Email Alerts",
                value=self.alerts_enabled,
                on_change=self.callbacks.get("toggle_alerts", lambda value: None),
            ).classes("mb-3")

            # Email settings
            with ui.column().classes("gap-3"):
                self.email_input = ui.input(
                    "Alert Email Address",
                    placeholder="user@example.com",
                    value=self.settings.get("email", "user@example.com"),
                ).classes("w-full")

                self.alert_delay_input = ui.number(
                    "Alert Delay (minutes)",
                    value=self.settings.get("alert_delay", 5),
                    min=1,
                    max=60,
                ).classes("w-full")

                ui.label("Send alert if no motion detected for this duration").classes(
                    "text-xs text-gray-600"
                )

            # Alert conditions
            ui.separator().classes("my-3")
            ui.label("Alert Conditions").classes("text-sm font-semibold")

            with ui.column().classes("ml-4 gap-1"):
                self.no_motion_alert = ui.checkbox(
                    "No motion detected (extended period)", value=True
                )
                self.camera_offline_alert = ui.checkbox(
                    "Camera goes offline", value=True
                )
                self.system_error_alert = ui.checkbox("System errors occur", value=True)
                self.experiment_complete_alert = ui.checkbox(
                    "Experiment completes", value=False
                )

            # Test and status
            ui.separator().classes("my-3")
            with ui.row().classes("gap-2 w-full"):
                ui.button(
                    "Send Test Alert",
                    icon="send",
                    on_click=self.callbacks.get("send_test_alert", lambda: None),
                ).props("color=warning").classes("flex-1")
                ui.button(
                    "Alert History",
                    icon="history",
                    on_click=self.callbacks.get("show_alert_history", lambda: None),
                ).props("color=secondary outline").classes("flex-1")

            # Last alert status
            self.last_alert_label = ui.label("No alerts sent").classes(
                "text-xs text-gray-600 mt-2"
            )
