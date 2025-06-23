from nicegui import ui, events
import asyncio
import inspect
from cvd.gui.ui_helpers import notify_later


# Default values for UVC camera controls
UVC_DEFAULTS = {
    "brightness": 0,
    "contrast": 100,
    "saturation": 100,
    "hue": 0,
    "sharpness": 50,
    "gain": 50,
    "gamma": 100,
    "backlight_compensation": 0,
    "white_balance_auto": True,
    "white_balance": 5000,
    "exposure_auto": True,
    "exposure": 100,
}


def create_uvc_control(label, min_val, max_val, default, callback):
    """Return bound number and slider widgets for a UVC control."""
    ui.label(label).classes("text-xs text-gray-600")
    with ui.row().classes("gap-3 items-center mb-3 w-full"):
        number = (
            ui.number(
                value=default,
                min=min_val,
                max=max_val,
                step=1,
                on_change=callback,
            )
            .classes("w-20")
            .props("dense outlined")
        )
        slider = (
            ui.slider(
                min=min_val,
                max=max_val,
                value=default,
                step=1,
                on_change=callback,
            )
            .props("thumb-label")
            .classes("flex-1")
            .style("min-width: 200px; height: 40px;")
        )

        slider.bind_value(number, "value")
        number.bind_value(slider, "value")

    return number, slider


class WebcamStreamElement:
    """Initialize webcam stream element with settings and optional callbacks"""

    # Track whether the /webcam_stream page has been registered
    _page_registered = False

    def __init__(
        self,
        settings,
        callbacks=None,
        on_camera_status_change=None,
        camera_toggle_cb=None,
        *,
        available_resolutions=None,
        available_devices=None,
    ):
        self.camera_active = False
        self.recording = False
        self._on_camera_status_change = on_camera_status_change
        settings = settings or {
            "sensitivity": 50,
            "fps": 30,
            "roi_enabled": False,
            "rotation": 0,
        }
        self.settings = settings
        self.callbacks = callbacks or {}
        self.available_resolutions = available_resolutions or []
        self.available_devices = available_devices or []
        # Store explicit camera toggle callback or look it up in callbacks dict
        self._camera_toggle_cb = camera_toggle_cb or self.callbacks.get("camera_toggle")
        # Callback for ROI updates (defaults to callbacks['set_roi'])
        self._roi_update_cb = self.callbacks.get("set_roi")
        # Store currently selected ROI
        self.roi_x = 0
        self.roi_y = 0
        self.roi_width = 0
        self.roi_height = 0
        self.roi_overlay = None
        self.camera_settings_expansion = None

        # Register the page only once for the first created instance
        if not WebcamStreamElement._page_registered:

            @ui.page("/webcam_stream")
            def webcam_stream_page():
                # Create the camera section
                self.create_camera_section()

            WebcamStreamElement._page_registered = True

    def create_camera_section(self):
        """Create camera feed and controls section"""
        with ui.card().classes("cvd-card w-full"):
            ui.label("Live Camera Feed").classes("text-lg font-bold mb-2")

            # Live camera stream from the /video_feed endpoint
            with ui.row().classes("justify-center mb-4"):
                # Determine initial aspect ratio from available resolutions
                if self.available_resolutions:
                    init_w, init_h = self.available_resolutions[0][:2]
                else:
                    init_w, init_h = 640, 480

                style = (
                    "width: 100%; "
                    f"aspect-ratio: {init_w}/{init_h}; "
                    "background-color: #f5f5f5; "
                    "display: flex; align-items: center; justify-content: center;"
                )

                with (
                    ui.card()
                    .classes("border-2 border-dashed border-gray-300")
                    .style(style)
                ) as container:
                    self.video_container = container

                    # Image element displaying the MJPEG stream
                    # initialize without an active source; the stream will be
                    # assigned when playback starts
                    self.video_element = ui.image("").style(
                        "width: 100%; height: 100%; object-fit: contain;"
                    )
                    self.loading_spinner = (
                        ui.spinner(size="2em")
                        .classes("absolute")
                        .style("top: 50%; left: 50%; transform: translate(-50%, -50%);")
                    )
                    self.video_element.on(
                        "load", lambda _: self.loading_spinner.set_visibility(False)
                    )
                    self.video_element.on(
                        "error",
                        lambda _: (
                            self.loading_spinner.set_visibility(False),
                            ui.notify(
                                "Failed to load video stream",
                                type="negative",
                            ),
                        ),
                    )
                    self.loading_spinner.set_visibility(True)

            # Camera controls
            with ui.row().classes("gap-2 justify-center mb-4"):
                self.start_camera_btn = ui.button(
                    "Play Video",
                    icon="play_arrow",
                    on_click=self.toggle_video_play,
                ).props("color=positive")
            # Collapsible Camera Settings
            with ui.expansion("Camera Settings", icon="settings") as exp:
                self.camera_settings_expansion = exp
                exp.classes("w-full mt-4")
                with ui.column().classes("gap-4 w-full mt-2"):
                    # Basic Camera Settings
                    ui.label("Basic Settings").classes(
                        "text-base font-semibold text-blue-600"
                    )

                    # Camera device selection
                    ui.label("Camera Device").classes(
                        "text-sm font-medium text-gray-700"
                    )
                    with ui.row().classes("gap-2 items-center mb-2"):
                        ui.button(
                            "Scan Cameras",
                            icon="search",
                            on_click=self.callbacks.get("scan_cameras", lambda: None),
                        ).props("size=sm")
                        self.device_select = (
                            ui.select(
                                self.available_devices,
                                label="Device",
                                value=(
                                    self.available_devices[0]
                                    if self.available_devices
                                    else None
                                ),
                                on_change=self.callbacks.get(
                                    "select_camera", lambda e: None
                                ),
                            )
                            .classes("w-full")
                            .props("dense outlined")
                        )

                    # Motion Sensitivity
                    ui.label("Motion Sensitivity").classes(
                        "text-sm font-medium text-gray-700"
                    )
                    with ui.row().classes("gap-3 items-center mb-3 w-full"):
                        self.sensitivity_number = (
                            ui.number(
                                value=self.settings["sensitivity"],
                                min=0,
                                max=100,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_sensitivity",
                                    lambda v: None,
                                ),
                            )
                            .classes("w-20")
                            .props("dense outlined")
                        )
                        self.sensitivity_slider = (
                            ui.slider(
                                min=0,
                                max=100,
                                value=self.settings["sensitivity"],
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_sensitivity",
                                    lambda v: None,
                                ),
                            )
                            .props("thumb-label")
                            .classes("flex-1")
                            .style("min-width: 200px; height: 40px;")
                        )

                        # Bind slider and number input values together
                        self.sensitivity_slider.bind_value(
                            self.sensitivity_number, "value"
                        )
                        self.sensitivity_number.bind_value(
                            self.sensitivity_slider, "value"
                        )

                    # Frame Rate, Resolution & Rotation
                    with ui.grid(columns=3).classes("gap-4 w-full mb-4"):
                        with ui.column():
                            ui.label("Frame Rate").classes(
                                "text-sm font-medium text-gray-700"
                            )
                            self.fps_select = (
                                ui.select(
                                    [5, 10, 15, 20, 24, 30],
                                    label="FPS",
                                    value=self.settings["fps"],
                                    on_change=self.callbacks.get(
                                        "update_fps",
                                        lambda v: None,
                                    ),
                                )
                                .classes("w-full")
                                .props("dense outlined")
                            )

                        with ui.column():
                            ui.label("Resolution").classes(
                                "text-sm font-medium text-gray-700"
                            )
                            options = [
                                f"{w}x{h} ({fps}fps)"
                                for (w, h, fps) in self.available_resolutions
                            ] or [
                                "320x240 (30fps)",
                                "352x288 (30fps)",
                                "640x480 (30fps)",
                                "800x600 (30fps)",
                                "1024x768 (30fps)",
                                "1280x720 (30fps)",
                                "1280x960 (30fps)",
                                "1280x1024 (30fps)",
                                "1920x1080 (30fps)",
                            ]
                            default_value = options[0] if options else "640x480 (30fps)"
                            self.resolution_select = (
                                ui.select(
                                    options,
                                    label="Resolution",
                                    value=default_value,
                                    on_change=self.callbacks.get(
                                        "update_resolution",
                                        lambda v: None,
                                    ),
                                )
                                .classes("w-full")
                                .props("dense outlined")
                            )

                        with ui.column():
                            ui.label("Rotation").classes(
                                "text-sm font-medium text-gray-700"
                            )
                            self.rotation_select = (
                                ui.select(
                                    [0, 90, 180, 270],
                                    label="Rotation",
                                    value=self.settings.get("rotation", 0),
                                    on_change=self.callbacks.get(
                                        "update_rotation",
                                        lambda v: None,
                                    ),
                                )
                                .classes("w-full")
                                .props("dense outlined")
                            )

                    # Region of Interest
                    ui.label("Region of Interest").classes(
                        "text-sm font-medium text-gray-700"
                    )
                    with ui.row().classes("gap-2 mb-4"):
                        self.roi_checkbox = ui.checkbox(
                            "Enable ROI", value=self.settings["roi_enabled"]
                        )
                        ui.button(
                            "Set ROI",
                            icon="crop_free",
                            on_click=self.callbacks.get(
                                "set_roi",
                                lambda: None,
                            ),
                        ).props("size=sm")

                    # UVC Camera Controls Section
                    ui.separator().classes("my-4")
                    ui.label("UVC Camera Controls").classes(
                        "text-base font-semibold text-blue-600"
                    )
                    ui.label("Hardware-level camera adjustments").classes(
                        "text-xs text-gray-600 mb-3"
                    )

                    # Image Quality Controls
                    ui.label("Image Quality").classes(
                        "text-sm font-medium text-gray-700 mb-2"
                    )  # Brightness Control
                    (
                        self.brightness_number,
                        self.brightness_slider,
                    ) = create_uvc_control(
                        "Brightness",
                        -100,
                        100,
                        UVC_DEFAULTS["brightness"],
                        self.callbacks.get("update_brightness", lambda value: None),
                    )

                    # Contrast Control
                    (
                        self.contrast_number,
                        self.contrast_slider,
                    ) = create_uvc_control(
                        "Contrast",
                        0,
                        200,
                        UVC_DEFAULTS["contrast"],
                        self.callbacks.get("update_contrast", lambda value: None),
                    )

                    # Saturation Control
                    (
                        self.saturation_number,
                        self.saturation_slider,
                    ) = create_uvc_control(
                        "Saturation",
                        0,
                        200,
                        UVC_DEFAULTS["saturation"],
                        self.callbacks.get("update_saturation", lambda value: None),
                    )

                    # Hue Control
                    (
                        self.hue_number,
                        self.hue_slider,
                    ) = create_uvc_control(
                        "Hue",
                        -180,
                        180,
                        UVC_DEFAULTS["hue"],
                        self.callbacks.get("update_hue", lambda value: None),
                    )

                    # Sharpness Control
                    (
                        self.sharpness_number,
                        self.sharpness_slider,
                    ) = create_uvc_control(
                        "Sharpness",
                        0,
                        100,
                        UVC_DEFAULTS["sharpness"],
                        self.callbacks.get("update_sharpness", lambda value: None),
                    )
                    # Exposure & Advanced Controls
                    ui.label("Exposure & Advanced").classes(
                        "text-sm font-medium text-gray-700 mb-2"
                    )

                    # White Balance Control
                    ui.label("White Balance").classes("text-xs text-gray-600")
                    with ui.row().classes("gap-3 mb-3 items-center w-full"):
                        # Auto/manual toggle for white balance
                        self.wb_auto_checkbox = ui.checkbox(
                            "Auto",
                            value=UVC_DEFAULTS["white_balance_auto"],
                            on_change=self.toggle_white_balance_auto,
                        ).classes("text-xs")
                        self.wb_manual_number = (
                            ui.number(
                                value=UVC_DEFAULTS["white_balance"],
                                min=2800,
                                max=6500,
                                step=100,
                                on_change=self.callbacks.get(
                                    "update_white_balance_manual",
                                    lambda value: None,
                                ),
                            )
                            .classes("w-24")
                            .props("dense outlined")
                        )
                        self.wb_manual_slider = (
                            ui.slider(
                                min=2800,
                                max=6500,
                                value=UVC_DEFAULTS["white_balance"],
                                step=100,
                                on_change=self.callbacks.get(
                                    "update_white_balance_manual",
                                    lambda value: None,
                                ),
                            )
                            .props("thumb-label")
                            .classes("flex-1")
                            .style("min-width: 200px; height: 40px;")
                        )

                        # Disable manual controls since auto is default
                        self.wb_manual_number.disable()
                        self.wb_manual_slider.disable()

                        # Bind values
                        self.wb_manual_slider.bind_value(self.wb_manual_number, "value")
                        self.wb_manual_number.bind_value(self.wb_manual_slider, "value")

                    # Exposure Control
                    ui.label("Exposure").classes("text-xs text-gray-600")
                    with ui.row().classes("gap-3 mb-3 items-center w-full"):
                        # Auto/manual toggle for exposure
                        self.exposure_auto_checkbox = ui.checkbox(
                            "Auto",
                            value=UVC_DEFAULTS["exposure_auto"],
                            on_change=self.toggle_exposure_auto,
                        ).classes("text-xs")
                        self.exposure_manual_number = (
                            ui.number(
                                value=UVC_DEFAULTS["exposure"],
                                min=1,
                                max=1000,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_exposure_manual",
                                    lambda value: None,
                                ),
                            )
                            .classes("w-24")
                            .props("dense outlined")
                        )
                        self.exposure_manual_slider = (
                            ui.slider(
                                min=1,
                                max=1000,
                                value=UVC_DEFAULTS["exposure"],
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_exposure_manual",
                                    lambda value: None,
                                ),
                            )
                            .props("thumb-label")
                            .classes("flex-1")
                            .style("min-width: 200px; height: 40px;")
                        )

                        # note: on_change passed above in constructor

                        # Disable manual controls as auto is default
                        self.exposure_manual_number.disable()
                        self.exposure_manual_slider.disable()
                        # Bind values
                        self.exposure_manual_slider.bind_value(
                            self.exposure_manual_number, "value"
                        )
                        self.exposure_manual_number.bind_value(
                            self.exposure_manual_slider, "value"
                        )

                    # Gain Control
                    (
                        self.gain_number,
                        self.gain_slider,
                    ) = create_uvc_control(
                        "Gain",
                        0,
                        100,
                        UVC_DEFAULTS["gain"],
                        self.callbacks.get("update_gain", lambda value: None),
                    )

                    # Gamma Control
                    (
                        self.gamma_number,
                        self.gamma_slider,
                    ) = create_uvc_control(
                        "Gamma",
                        50,
                        300,
                        UVC_DEFAULTS["gamma"],
                        self.callbacks.get("update_gamma", lambda value: None),
                    )

                    # Backlight Compensation Control
                    (
                        self.backlight_comp_number,
                        self.backlight_comp_slider,
                    ) = create_uvc_control(
                        "Backlight Compensation",
                        0,
                        100,
                        UVC_DEFAULTS["backlight_compensation"],
                        self.callbacks.get("update_backlight_comp", lambda value: None),
                    )

                    # UVC Control Buttons
                    with ui.row().classes("gap-2 mt-4 justify-end"):
                        ui.button(
                            "Reset to Defaults",
                            icon="restore",
                            on_click=self.callbacks.get(
                                "reset_uvc_defaults", lambda: None
                            ),
                        ).props("size=sm color=orange")
                        ui.button(
                            "Apply UVC Settings",
                            icon="check",
                            on_click=self.callbacks.get(
                                "apply_uvc_settings", lambda: None
                            ),
                        ).props("size=sm")

    async def toggle_video_play(self):
        """Toggle video play state"""
        start_camera = not self.camera_active

        result = True

        if self._camera_toggle_cb:
            if inspect.iscoroutinefunction(self._camera_toggle_cb):
                result = await self._camera_toggle_cb()
            else:
                result = await asyncio.to_thread(self._camera_toggle_cb)

        if start_camera:
            if result:
                self.video_element.set_source("/video_feed")
                if hasattr(self, "loading_spinner"):
                    self.loading_spinner.set_visibility(True)

                self.start_camera_btn.set_text("Pause Video")
                self.start_camera_btn.set_icon("pause")
                self.start_camera_btn.props("color=negative")
                self.camera_active = True
                self._update_status()
            else:
                notify_later("Failed to start camera", type="negative")
        else:
            if result:
                if self.video_element.source:
                    self.video_element.set_source("")
                self.start_camera_btn.set_text("Play Video")
                self.start_camera_btn.set_icon("play_arrow")
                self.start_camera_btn.props("color=positive")
                self.camera_active = False
                self._update_status()
            else:
                notify_later("Failed to stop camera", type="negative")

    def toggle_white_balance_auto(self, value):
        """Toggle auto/manual white balance"""
        if value:
            self.wb_manual_number.disable()
            self.wb_manual_slider.disable()
        else:
            self.wb_manual_number.enable()
            self.wb_manual_slider.enable()

    def toggle_exposure_auto(self, value):
        """Toggle auto/manual exposure"""
        if value:
            self.exposure_manual_number.disable()
            self.exposure_manual_slider.disable()
        else:
            self.exposure_manual_number.enable()
            self.exposure_manual_slider.enable()

    def _update_status(self):
        """Notify parent about camera state changes."""
        if self._on_camera_status_change:
            self._on_camera_status_change(self.camera_active)

    def toggle_recording(self):
        """Stub method for compatibility."""
        pass

    def take_snapshot(self):
        """Stub method for compatibility."""
        pass

    def adjust_roi(self):
        """Stub method for compatibility."""
        pass

    def show_camera_settings(self):
        """Open the camera settings expansion from the context menu."""
        if self.camera_settings_expansion is not None:
            self.camera_settings_expansion.open()

    def reset_view(self):
        """Stub method for compatibility."""
        pass

    def update_video_aspect(self, width: int, height: int) -> None:
        """Update video container aspect ratio."""
        if not getattr(self, "video_container", None):
            return
        if width <= 0 or height <= 0:
            return
        style = (
            "width: 100%; "
            f"aspect-ratio: {width}/{height}; "
            "background-color: #f5f5f5; "
            "display: flex; align-items: center; justify-content: center;"
        )
        self.video_container.style(style)

    def swap_video_container_dimensions(self):
        """Swap the width and height of the video container."""
        if not hasattr(self, "video_container"):
            return
        style = getattr(self.video_container, "_style", {})
        width = style.get("width")
        height = style.get("height")
        if width and height:
            self.video_container.style(f"width: {height}; height: {width};")

    def update_resolutions(self, modes):
        """Update resolution dropdown options."""
        self.available_resolutions = list(modes or [])
        options = [f"{w}x{h} ({fps}fps)" for (w, h, fps) in self.available_resolutions]
        if hasattr(self, "resolution_select"):
            current = getattr(self.resolution_select, "value", None)
            self.resolution_select.options = options
            if current not in options and options:
                self.resolution_select.value = options[0]

    def update_devices(self, devices):
        """Update available camera device dropdown options."""
        self.available_devices = list(devices or [])
        if hasattr(self, "device_select"):
            current = getattr(self.device_select, "value", None)
            self.device_select.options = self.available_devices
            if current not in self.available_devices and self.available_devices:
                self.device_select.value = self.available_devices[0]

    def refresh_roi_overlay(self):
        """Update the ROI overlay based on current settings."""
        if not getattr(self, "roi_overlay", None):
            return
        visible = (
            getattr(self, "roi_checkbox", None)
            and self.roi_checkbox.value
            and self.roi_width > 0
            and self.roi_height > 0
        )
        if visible:
            self.roi_overlay.content = (
                f'<svg width="100%" height="100%">'
                f'<rect x="{self.roi_x}" y="{self.roi_y}" '
                f'width="{self.roi_width}" height="{self.roi_height}" '
                f'style="fill:none;stroke:red;stroke-width:2"/>'
                f"</svg>"
            )
        else:
            self.roi_overlay.content = ""
