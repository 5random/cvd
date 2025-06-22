"""UI elements for configuring and testing basic email alerts."""

from nicegui import ui


class EmailAlertsSection:
    """Section for managing email alert settings within the GUI."""
    def __init__(self, settings, callbacks=None):
        """Initialize email alerts section with settings"""
        self.experiment_running = False
        self.alerts_enabled = False
        settings = settings or {}
        settings.setdefault("email", "user@example.com")
        settings.setdefault("alert_delay", 5)
        # ensure keys for all alerts exist with sensible defaults
        settings.setdefault("no_motion_alert", True)
        settings.setdefault("camera_offline_alert", True)
        settings.setdefault("system_error_alert", True)
        settings.setdefault("experiment_complete_alert", False)
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
            self.alerts_enabled_checkbox = (
                ui.checkbox(
                    "Enable Email Alerts",
                    value=self.alerts_enabled,
                    on_change=self.callbacks.get(
                        "toggle_alerts",
                        lambda value: None,
                    ),
                ).classes("mb-3")
            )

            # Email settings
            with ui.column().classes("gap-3"):

                self.email_input = (
                    ui.input(
                        "Alert Email Address",
                        placeholder="user@example.com",
                        value=self.settings["email"],
                    )
                    .on("update:model-value", self._on_email_change)
                    .classes("w-full")
                )

                self.alert_delay_input = (
                    ui.number(
                        "Alert Delay (minutes)",
                        value=self.settings["alert_delay"],
                        min=1,
                        max=60,
                    )
                    .on("update:model-value", self._on_delay_change)
                    .classes("w-full")
                )


                ui.label(
                    "Send alert if no motion detected for this duration"
                ).classes(
                    "text-xs text-gray-600"
                )

            # Alert conditions
            ui.separator().classes("my-3")
            ui.label("Alert Conditions").classes("text-sm font-semibold")

            with ui.column().classes("ml-4 gap-1"):
                self.no_motion_alert = ui.checkbox(
                    "No motion detected (extended period)",
                    value=self.settings.get("no_motion_alert", True),
                    on_change=lambda e: self._on_checkbox_change(
                        "no_motion_alert", e.value
                    ),
                )
                self.camera_offline_alert = ui.checkbox(
                    "Camera goes offline",
                    value=self.settings.get("camera_offline_alert", True),
                    on_change=lambda e: self._on_checkbox_change(
                        "camera_offline_alert", e.value
                    ),
                )
                self.system_error_alert = ui.checkbox(
                    "System errors occur",
                    value=self.settings.get("system_error_alert", True),
                    on_change=lambda e: self._on_checkbox_change(
                        "system_error_alert", e.value
                    ),
                )

                self.system_error_alert = ui.checkbox(
                    "System errors occur",
                    value=True,
                )

                self.experiment_complete_alert = ui.checkbox(
                    "Experiment completes",
                    value=self.settings.get("experiment_complete_alert", False),
                    on_change=lambda e: self._on_checkbox_change(
                        "experiment_complete_alert", e.value
                    ),
                )

            # Test and status
            ui.separator().classes("my-3")
            with ui.row().classes("gap-2 w-full"):
                ui.button(
                    "Send Test Alert",
                    icon="send",
                    on_click=self.callbacks.get(
                        "send_test_alert",
                        lambda: None,
                    ),
                ).props("color=warning").classes("flex-1")
                ui.button(
                    "Alert History",
                    icon="history",
                    on_click=self.callbacks.get(
                        "show_alert_history",
                        lambda: None,
                    ),
                ).props("color=secondary outline").classes("flex-1")

            # Last alert status
            self.last_alert_label = ui.label("No alerts sent").classes(
                "text-xs text-gray-600 mt-2"
            )

    def _on_email_change(self, event) -> None:
        """Update email setting from input."""
        value = getattr(event, "value", None)
        if value is not None:
            self.settings["email"] = value
            callback = self.callbacks.get("update_email")
            if callback:
                callback(value)

    def _on_delay_change(self, event) -> None:
        """Update alert delay setting from input."""
        value = getattr(event, "value", None)
        if value is not None:
            try:
                self.settings["alert_delay"] = int(value)
            except (TypeError, ValueError):
                return
            callback = self.callbacks.get("update_alert_delay")
            if callback:
                callback(self.settings["alert_delay"])

    def _on_checkbox_change(self, key: str, value: bool) -> None:
        """Handle checkbox value changes."""
        self.settings[key] = bool(value)
        callback = self.callbacks.get(key)
        if callback:
            callback(bool(value))
