"""Setup wizard component using NiceGUI stepper for initial configuration."""

from typing import Any, Optional, Callable
from nicegui import ui

from src.gui.gui_tab_components.gui_tab_base_component import (
    BaseComponent,
    ComponentConfig,
)
from src.gui.gui_tab_components.gui_tab_sensors_component import SensorConfigDialog
from src.gui.gui_tab_components.gui_tab_controllers_component import (
    ControllerConfigDialog,
)
from src.data_handler.sources.sensor_source_manager import SensorManager
from src.controllers.controller_manager import ControllerManager
from src.utils.config_utils.config_service import ConfigurationService


class SetupWizardComponent(BaseComponent):
    """Wizard to guide initial setup of sensors and controllers."""

    def __init__(
        self,
        config_service: ConfigurationService,
        sensor_manager: SensorManager,
        controller_manager: ControllerManager,
    ):
        config = ComponentConfig(component_id="setup_wizard")
        super().__init__(config)
        self.config_service = config_service
        self.sensor_manager = sensor_manager
        self.controller_manager = controller_manager

        self._dialog: Optional[ui.dialog] = None

        self._sensor_dialog = SensorConfigDialog(
            config_service, sensor_manager, self._refresh_sensors
        )
        self._controller_dialog = ControllerConfigDialog(
            config_service, controller_manager, self._refresh_controllers
        )

        self._stepper: ui.stepper | None = None
        self._sensor_list: ui.column | None = None
        self._controller_list: ui.column | None = None
        self._dialog: ui.dialog | None = None

    def render(self) -> ui.column:
        """Render stepper UI."""
        with ui.column().classes("w-full") as root:
            with ui.stepper().props("vertical") as self._stepper:
                # Sensors step
                with ui.step("sensors", title="Sensoren einrichten", icon="sensors"):
                    ui.label(
                        "Füge Sensoren hinzu, die verwendet werden sollen."
                    ).classes("mb-2")
                    ui.button(
                        "Sensor hinzufügen",
                        on_click=self._sensor_dialog.show_add_dialog,
                    ).props("color=primary")
                    self._sensor_list = ui.column().classes("mt-2")
                    self._refresh_sensors()
                    with ui.stepper_navigation():
                        ui.button("Weiter", on_click=self._stepper.next).props(
                            "color=primary"
                        )
                # Controllers step
                with ui.step("controllers", title="Controller einrichten", icon="tune"):
                    ui.label(
                        "Füge Controller hinzu, die genutzt werden sollen."
                    ).classes("mb-2")
                    ui.button(
                        "Controller hinzufügen",
                        on_click=self._controller_dialog.show_add_dialog,
                    ).props("color=primary")
                    self._controller_list = ui.column().classes("mt-2")
                    self._refresh_controllers()
                    with ui.stepper_navigation():
                        ui.button("Zurück", on_click=self._stepper.previous)
                        ui.button("Weiter", on_click=self._stepper.next).props(
                            "color=primary"
                        )
                # Finish step
                with ui.step("finish", title="Abschließen", icon="check"):
                    ui.label("Einrichtung abgeschlossen.").classes("mb-2")
                    ui.button(
                        "Zum Dashboard", on_click=lambda: ui.navigate.to("/")
                    ).props("color=primary")
                    with ui.stepper_navigation():
                        ui.button("Zurück", on_click=self._stepper.previous)
        self._rendered = True
        self._element = root
        return root

    def _refresh_sensors(self) -> None:
        if not self._sensor_list:
            return
        self._sensor_list.clear()
        for sensor_id, cfg in self.config_service.get_sensor_configs():
            with self._sensor_list:
                ui.label(f"{sensor_id}: {cfg.get('name', sensor_id)}").classes(
                    "text-sm"
                )

    def _refresh_controllers(self) -> None:
        if not self._controller_list:
            return
        self._controller_list.clear()
        for controller_id, cfg in self.config_service.get_controller_configs():
            with self._controller_list:
                ui.label(f"{controller_id}: {cfg.get('name', controller_id)}").classes(
                    "text-sm"
                )

    def show_dialog(self, start_step: str) -> None:
        """Open the setup wizard in a dialog starting at the given step."""
        with ui.dialog().props("persistent") as dialog:
            self._dialog = dialog
            with ui.card().classes("w-[600px] max-w-[90vw]"):
                self.render()

        if self._stepper:
            try:
                self._stepper.set_value(start_step)
            except Exception:
                pass

        self._refresh_sensors()
        self._refresh_controllers()

        dialog.open()

    def close_dialog(self) -> None:
        """Close the setup wizard dialog if open."""
        if self._dialog:
            self._dialog.close()

    def _update_element(self, data: Any) -> None:
        """Refresh sensor and controller lists when configuration changes."""
        self._refresh_sensors()
        self._refresh_controllers()

    def show_dialog(
        self,
        start_step: str = "sensors",
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """Display the setup wizard inside a dialog."""
        with ui.dialog().props("persistent") as dialog:
            self._dialog = dialog
            with ui.card().classes("w-[600px] max-w-[90vw]"):
                self.render()
                if self._stepper:
                    self._stepper.active = start_step
            if on_close:
                dialog.on("close", lambda _: on_close())
        dialog.open()
