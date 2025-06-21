from nicegui import ui


class WebcamStreamElement:
    """Initialize webcam stream element with settings and optional callbacks"""

    def __init__(self, settings, callbacks=None, on_camera_status_change=None):
        self.camera_active = False
        self.recording = False
        self._on_camera_status_change = on_camera_status_change
        settings = settings or {"sensitivity": 50, "fps": 30, "roi_enabled": False}
        self.settings = settings
        self.callbacks = callbacks or {}

        @ui.page("/webcam_stream")
        def webcam_stream_page():
            # Create the camera section
            self.create_camera_section()

    def create_camera_section(self):
        """Create camera feed and controls section"""
        with ui.card().classes("cvd-card w-full"):
            ui.label("Live Camera Feed").classes("text-lg font-bold mb-2")

            # Live camera stream from the /video_feed endpoint
            with ui.row().classes("justify-center mb-4"):
                with (
                    ui.card()
                    .classes("border-2 border-dashed border-gray-300")
                    .style(
                        "width: 640px; height: 480px; background-color: #f5f5f5; display: flex; align-items: center; justify-content: center;"
                    )
                ):
                    # Video element displaying the MJPEG stream
                    self.video_element = ui.video("/video_feed").style(
                        "width: 100%; height: 100%; object-fit: contain;"
                    )

                    # Right-click context menu for camera
                    with ui.context_menu():
                        ui.menu_item(
                            "Camera Settings",
                            on_click=self.callbacks.get(
                                "show_camera_settings", lambda: None
                            ),
                        )
                        ui.separator()
                        ui.menu_item(
                            "Take Snapshot",
                            on_click=self.callbacks.get(
                                "take_snapshot", self.take_snapshot
                            ),
                        )
                        ui.separator()
                        ui.menu_item(
                            "Adjust ROI",
                            on_click=self.callbacks.get("adjust_roi", self.adjust_roi),
                        )
                        ui.menu_item(
                            "Reset View",
                            on_click=self.callbacks.get("reset_view", lambda: None),
                        )
                        # Recording toggle menu item
                        self.record_menu_item = ui.menu_item(
                            "Start Recording",
                            on_click=self.toggle_recording,
                        )

            # Camera controls
            with ui.row().classes("gap-2 justify-center mb-4"):
                self.start_camera_btn = ui.button(
                    "Play Video", icon="play_arrow", on_click=self.toggle_video_play
                ).props("color=positive")
                self.stop_camera_btn = ui.button(
                    "Pause Video", icon="pause", on_click=self.toggle_video_pause
                ).props("color=negative")
            # Collapsible Camera Settings
            with ui.expansion("Camera Settings", icon="settings").classes(
                "w-full mt-4"
            ):
                with ui.column().classes("gap-4 w-full mt-2"):
                    # Basic Camera Settings
                    ui.label("Basic Settings").classes(
                        "text-base font-semibold text-blue-600"
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

                    # Frame Rate & Resolution
                    with ui.grid(columns=2).classes("gap-4 w-full mb-4"):
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
                            self.resolution_select = (
                                ui.select(
                                    [
                                        "320x240 (30fps)",
                                        "352x288 (30fps)",
                                        "640x480 (30fps)",
                                        "800x600 (30fps)",
                                        "1024x768 (30fps)",
                                        "1280x720 (30fps)",
                                        "1280x960 (30fps)",
                                        "1280x1024 (30fps)",
                                        "1920x1080 (30fps)",
                                    ],
                                    label="Resolution",
                                    value="640x480 (30fps)",
                                    on_change=self.callbacks.get(
                                        "update_resolution",
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
                    ui.label("Brightness").classes("text-xs text-gray-600")
                    with ui.row().classes("gap-3 items-center mb-3 w-full"):
                        self.brightness_number = (
                            ui.number(
                                value=0,
                                min=-100,
                                max=100,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_brightness", lambda value: None
                                ),
                            )
                            .classes("w-20")
                            .props("dense outlined")
                        )
                        self.brightness_slider = (
                            ui.slider(
                                min=-100,
                                max=100,
                                value=0,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_brightness", lambda value: None
                                ),
                            )
                            .props("thumb-label")
                            .classes("flex-1")
                            .style("min-width: 200px; height: 40px;")
                        )

                        # Bind values
                        self.brightness_slider.bind_value(
                            self.brightness_number, "value"
                        )
                        self.brightness_number.bind_value(
                            self.brightness_slider, "value"
                        )

                    # Contrast Control
                    ui.label("Contrast").classes("text-xs text-gray-600")
                    with ui.row().classes("gap-3 items-center mb-3 w-full"):
                        self.contrast_number = (
                            ui.number(
                                value=100,
                                min=0,
                                max=200,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_contrast", lambda value: None
                                ),
                            )
                            .classes("w-20")
                            .props("dense outlined")
                        )
                        self.contrast_slider = (
                            ui.slider(
                                min=0,
                                max=200,
                                value=100,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_contrast", lambda value: None
                                ),
                            )
                            .props("thumb-label")
                            .classes("flex-1")
                            .style("min-width: 200px; height: 40px;")
                        )

                        # Bind values
                        self.contrast_slider.bind_value(self.contrast_number, "value")
                        self.contrast_number.bind_value(self.contrast_slider, "value")

                    # Saturation Control
                    ui.label("Saturation").classes("text-xs text-gray-600")
                    with ui.row().classes("gap-3 items-center mb-3 w-full"):
                        self.saturation_number = (
                            ui.number(
                                value=100,
                                min=0,
                                max=200,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_saturation", lambda value: None
                                ),
                            )
                            .classes("w-20")
                            .props("dense outlined")
                        )
                        self.saturation_slider = (
                            ui.slider(
                                min=0,
                                max=200,
                                value=100,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_saturation", lambda value: None
                                ),
                            )
                            .props("thumb-label")
                            .classes("flex-1")
                            .style("min-width: 200px; height: 40px;")
                        )

                        # Bind values
                        self.saturation_slider.bind_value(
                            self.saturation_number, "value"
                        )
                        self.saturation_number.bind_value(
                            self.saturation_slider, "value"
                        )

                    # Hue Control
                    ui.label("Hue").classes("text-xs text-gray-600")
                    with ui.row().classes("gap-3 items-center mb-3 w-full"):
                        self.hue_number = (
                            ui.number(
                                value=0,
                                min=-180,
                                max=180,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_hue", lambda value: None
                                ),
                            )
                            .classes("w-20")
                            .props("dense outlined")
                        )
                        self.hue_slider = (
                            ui.slider(
                                min=-180,
                                max=180,
                                value=0,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_hue", lambda value: None
                                ),
                            )
                            .props("thumb-label")
                            .classes("flex-1")
                            .style("min-width: 200px; height: 40px;")
                        )

                        # Bind values
                        self.hue_slider.bind_value(self.hue_number, "value")
                        self.hue_number.bind_value(self.hue_slider, "value")

                    # Sharpness Control
                    ui.label("Sharpness").classes("text-xs text-gray-600")
                    with ui.row().classes("gap-3 items-center mb-4 w-full"):
                        self.sharpness_number = (
                            ui.number(
                                value=50,
                                min=0,
                                max=100,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_sharpness", lambda value: None
                                ),
                            )
                            .classes("w-20")
                            .props("dense outlined")
                        )
                        self.sharpness_slider = (
                            ui.slider(
                                min=0,
                                max=100,
                                value=50,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_sharpness", lambda value: None
                                ),
                            )
                            .props("thumb-label")
                            .classes("flex-1")
                            .style("min-width: 200px; height: 40px;")
                        )

                        # Bind values
                        self.sharpness_slider.bind_value(self.sharpness_number, "value")
                        self.sharpness_number.bind_value(self.sharpness_slider, "value")
                    # Exposure & Advanced Controls
                    ui.label("Exposure & Advanced").classes(
                        "text-sm font-medium text-gray-700 mb-2"
                    )

                    # White Balance Control
                    ui.label("White Balance").classes("text-xs text-gray-600")
                    with ui.row().classes("gap-3 mb-3 items-center w-full"):
                        # Auto/manual toggle for white balance
                        self.wb_auto_checkbox = ui.checkbox(
                            "Auto", value=True, on_change=self.toggle_white_balance_auto
                        ).classes("text-xs")
                        self.wb_manual_number = (
                            ui.number(
                                value=5000,
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
                                value=5000,
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

                        # Initially disable manual controls since auto is enabled by default
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
                            "Auto", value=True, on_change=self.toggle_exposure_auto
                        ).classes("text-xs")
                        self.exposure_manual_number = (
                            ui.number(
                                value=100,
                                min=1,
                                max=1000,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_exposure_manual", lambda value: None
                                ),
                            )
                            .classes("w-24")
                            .props("dense outlined")
                        )
                        self.exposure_manual_slider = (
                            ui.slider(
                                min=1,
                                max=1000,
                                value=100,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_exposure_manual", lambda value: None
                                ),
                            )
                            .props("thumb-label")
                            .classes("flex-1")
                            .style("min-width: 200px; height: 40px;")
                        )

                        # note: on_change passed above in constructor

                        # Initially disable manual controls since auto is enabled by default
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
                    ui.label("Gain").classes("text-xs text-gray-600")
                    with ui.row().classes("gap-3 items-center mb-3 w-full"):
                        self.gain_number = (
                            ui.number(
                                value=50,
                                min=0,
                                max=100,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_gain", lambda value: None
                                ),
                            )
                            .classes("w-20")
                            .props("dense outlined")
                        )
                        self.gain_slider = (
                            ui.slider(
                                min=0,
                                max=100,
                                value=50,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_gain", lambda value: None
                                ),
                            )
                            .props("thumb-label")
                            .classes("flex-1")
                            .style("min-width: 200px; height: 40px;")
                        )

                        # Bind values
                        self.gain_slider.bind_value(self.gain_number, "value")
                        self.gain_number.bind_value(self.gain_slider, "value")

                    # Gamma Control
                    ui.label("Gamma").classes("text-xs text-gray-600")
                    with ui.row().classes("gap-3 items-center mb-3 w-full"):
                        self.gamma_number = (
                            ui.number(
                                value=100,
                                min=50,
                                max=300,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_gamma", lambda value: None
                                ),
                            )
                            .classes("w-20")
                            .props("dense outlined")
                        )
                        self.gamma_slider = (
                            ui.slider(
                                min=50,
                                max=300,
                                value=100,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_gamma", lambda value: None
                                ),
                            )
                            .props("thumb-label")
                            .classes("flex-1")
                            .style("min-width: 200px; height: 40px;")
                        )

                        # Bind values
                        self.gamma_slider.bind_value(self.gamma_number, "value")
                        self.gamma_number.bind_value(self.gamma_slider, "value")

                    # Backlight Compensation Control
                    ui.label("Backlight Compensation").classes("text-xs text-gray-600")
                    with ui.row().classes("gap-3 items-center mb-4 w-full"):
                        self.backlight_comp_number = (
                            ui.number(
                                value=0,
                                min=0,
                                max=100,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_backlight_comp", lambda value: None
                                ),
                            )
                            .classes("w-20")
                            .props("dense outlined")
                        )
                        self.backlight_comp_slider = (
                            ui.slider(
                                min=0,
                                max=100,
                                value=0,
                                step=1,
                                on_change=self.callbacks.get(
                                    "update_backlight_comp", lambda value: None
                                ),
                            )
                            .props("thumb-label")
                            .classes("flex-1")
                            .style("min-width: 200px; height: 40px;")
                        )

                        # Bind values
                        self.backlight_comp_slider.bind_value(
                            self.backlight_comp_number, "value"
                        )
                        self.backlight_comp_number.bind_value(
                            self.backlight_comp_slider, "value"
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

    def toggle_video_play(self):
        """Toggle video play state"""
        if not self.camera_active:
            self.video_element.play()
            self.start_camera_btn.set_text("Pause Video")
            self.start_camera_btn.set_icon("pause")
            self.camera_active = True
            self._update_status()
        else:
            self.video_element.pause()
            self.start_camera_btn.set_text("Play Video")
            self.start_camera_btn.set_icon("play_arrow")
            self.camera_active = False
            self._update_status()

    def toggle_video_pause(self):
        """Toggle video pause state"""
        if self.camera_active:
            self.video_element.pause()
            self.start_camera_btn.set_text("Play Video")
            self.start_camera_btn.set_icon("play_arrow")
            self.camera_active = False
            self._update_status()
        else:
            self.video_element.play()
            self.start_camera_btn.set_text("Pause Video")
            self.start_camera_btn.set_icon("pause")
            self.camera_active = True
            self._update_status()

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
        """Start or stop dummy recording."""
        self.recording = not self.recording
        if self.recording:
            self.record_menu_item.update(text="Stop Recording")
            ui.notify("Recording started", type="positive")
        else:
            self.record_menu_item.update(text="Start Recording")
            ui.notify("Recording stopped", type="warning")

    def take_snapshot(self):
        """Capture a snapshot of the current video frame."""
        js = f"""
        const v = document.getElementById('{self.video_element.id}');
        const c = Object.assign(document.createElement('canvas'), {{width: v.videoWidth, height: v.videoHeight}});
        c.getContext('2d').drawImage(v, 0, 0);
        c.toBlob(b => {{
            const url = URL.createObjectURL(b);
            const a = Object.assign(document.createElement('a'), {{href: url, download: 'snapshot.png'}});
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}, 'image/png');
        """
        ui.run_javascript(js)

    def adjust_roi(self):
        """Open a simple ROI adjustment dialog."""
        with ui.dialog() as dialog, ui.card():
            ui.label("Adjust ROI - Demo")
            ui.slider(min=0, max=100, value=0, label="X start").props("dense")
            ui.slider(min=0, max=100, value=100, label="Width").props("dense")
            ui.button("Apply", on_click=dialog.close)
        dialog.open()
