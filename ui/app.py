import base64
import json
import logging
import os
import sys
from pathlib import Path

import cv2

from nicegui import ui, app

from src.camera import list_cameras
from src.head_tracker import HeadTracker, TrackerConfig
from src.obs_connector import OBSConnector

log = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get(
    "HEAD_TIMER_CONFIG",
    str(Path(__file__).resolve().parent.parent / "config.json"),
)
EXAMPLE_CONFIG_PATH = str(Path(__file__).resolve().parent.parent / "config.example.json")


class HeadTimerUI:
    def __init__(self):
        self.obs = OBSConnector()
        self.tracker = HeadTracker(self.obs)
        self.config = TrackerConfig()
        self._load_config()

        self._preview_html: ui.html | None = None
        self._obs_status: ui.label | None = None
        self._canvas_info: ui.label | None = None
        self._face_status: ui.label | None = None
        self._fps_label: ui.label | None = None
        self._pos_label: ui.label | None = None
        self._scene_select: ui.select | None = None
        self._timer_select: ui.select | None = None
        self._camera_select: ui.select | None = None
        self._device_camera_select: ui.select | None = None
        self._smoothing_slider: ui.slider | None = None
        self._rotation_checkbox: ui.checkbox | None = None
        self._offset_input: ui.number | None = None
        self._target_fps_slider: ui.slider | None = None
        self._start_button: ui.button | None = None
        self._stop_button: ui.button | None = None
        self._connect_button: ui.button | None = None
        self._camera_select_ui: ui.select | None = None
        self._last_preview_frame = None

        self._setup_page()

    def _load_config(self):
        if not os.path.exists(CONFIG_PATH):
            example_src = EXAMPLE_CONFIG_PATH
            if getattr(sys, "frozen", False):
                bundled = Path(sys._MEIPASS) / "config.example.json"
                if bundled.exists():
                    example_src = str(bundled)
            if os.path.exists(example_src):
                import shutil
                shutil.copy(example_src, CONFIG_PATH)
                log.info("Created config from example: %s", CONFIG_PATH)

        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)

            obs_cfg = data.get("obs", {})
            self.obs.host = obs_cfg.get("host", "localhost")
            self.obs.port = obs_cfg.get("port", 4455)
            self.obs.password = obs_cfg.get("password", "")

            trk = data.get("tracking", {})
            self.config.scene_name = trk.get("scene_name", "")
            self.config.timer_source_name = trk.get("timer_source_name", "")
            self.config.camera_source_name = trk.get("camera_source_name", "")
            self.config.smoothing_alpha = trk.get("smoothing_alpha", 0.3)
            self.config.rotation_enabled = trk.get("rotation_enabled", True)
            self.config.offset_y = trk.get("offset_y", 20)
            self.config.target_fps = trk.get("target_fps", 30.0)
            self.config.camera_index = trk.get("camera_index", 0)

            log.info(
                "Config loaded: scene='%s' timer='%s' camera='%s' smoothing=%.2f",
                self.config.scene_name,
                self.config.timer_source_name,
                self.config.camera_source_name,
                self.config.smoothing_alpha,
            )
        except (FileNotFoundError, json.JSONDecodeError):
            log.warning("No config found at %s, using defaults", CONFIG_PATH)

    def _save_config(self):
        data = {
            "obs": {
                "host": self.obs.host,
                "port": self.obs.port,
                "password": self.obs.password,
            },
            "tracking": {
                "scene_name": self.config.scene_name,
                "timer_source_name": self.config.timer_source_name,
                "camera_source_name": self.config.camera_source_name,
                "smoothing_alpha": self.config.smoothing_alpha,
                "rotation_enabled": self.config.rotation_enabled,
                "offset_y": self.config.offset_y,
                "target_fps": self.config.target_fps,
                "camera_index": self.config.camera_index,
            },
        }
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)
        log.debug("Config saved to %s", CONFIG_PATH)

    def _setup_page(self):
        @ui.page("/")
        def main():
            self._build_ui()
            ui.timer(0.016, self._update_preview)
            ui.timer(0.5, self._update_status)

        @ui.page("/settings")
        def settings():
            self._build_settings_page()

    def _build_settings_page(self):
        ui.label("OBS Connection").classes("text-h6")
        host = ui.input("Host", value=self.obs.host)
        port = ui.number("Port", value=self.obs.port, min=1, max=65535, format="%.0f")
        password = ui.input("Password", value=self.obs.password, password=True)

        def save_settings():
            self.obs.host = host.value or "localhost"
            self.obs.port = int(port.value or 4455)
            self.obs.password = password.value or ""
            self._save_config()
            ui.notify("Settings saved", type="positive")

        ui.button("Save", on_click=save_settings)
        ui.link("Back to main", "/").classes("mt-4 block")

    def _build_ui(self):
        with ui.header().classes("items-center justify-between"):
            ui.label("MisterTimer").classes("text-h5")
            with ui.row():
                self._connect_button = ui.button("Connect OBS", on_click=self._connect_to_obs)
                ui.link("Settings", "/settings").classes("text-white")

        with ui.row().classes("w-full gap-4 p-4"):
            with ui.column().classes("flex-1"):
                ui.label("Camera Preview").classes("text-subtitle1 mb-2")
                self._preview_html = ui.html("""
                    <canvas id="preview-canvas" style="max-width:640px; width:100%; border:1px solid #ccc; border-radius:4px; background:#111"></canvas>
                """)

            with ui.column().classes("w-80 gap-2"):
                with ui.card().classes("w-full"):
                    self._obs_status = ui.label("OBS: ⬤ Disconnected")
                    self._obs_help = ui.html("""
                        <div style="font-size: 0.8rem; color: #aaa; margin-top: 4px;">
                            Enable in OBS:<br>
                            <b>Tools → WebSocket Server Settings</b><br>
                            Check "Enable WebSocket server"<br>
                            Default port: 4455
                        </div>
                    """)
                    self._canvas_info = ui.label("")

                with ui.card().classes("w-full"):
                    ui.label("Sources").classes("text-subtitle1")
                    self._scene_select = ui.select(
                        label="Scene",
                        options=[],
                        on_change=self._on_scene_change,
                    ).classes("w-full")
                    self._timer_select = ui.select(
                        label="Timer Widget",
                        options=[],
                        on_change=self._on_timer_change,
                    ).classes("w-full")
                    self._camera_select = ui.select(
                        label="OBS Camera Source",
                        options=[],
                        on_change=self._on_camera_change,
                    ).classes("w-full")
                    self._device_camera_select = ui.select(
                        label="Capture Device",
                        options={},
                        on_change=self._on_device_camera_change,
                    ).classes("w-full")
                    self._populate_camera_devices()

                with ui.card().classes("w-full"):
                    ui.label("Tracking Settings").classes("text-subtitle1")
                    self._smoothing_slider = (
                        ui.slider(min=0.05, max=0.95, step=0.05, value=self.config.smoothing_alpha)
                        .props("label")
                        .classes("w-full")
                    )
                    ui.label().bind_text_from(
                        self._smoothing_slider, "value",
                        backward=lambda v: f"Smoothing: {v:.2f}",
                    )
                    self._rotation_checkbox = ui.checkbox(
                        "Enable Rotation",
                        value=self.config.rotation_enabled,
                    )
                    self._offset_input = ui.number(
                        "Y Offset (px)",
                        value=self.config.offset_y,
                        min=-100,
                        max=200,
                        format="%.0f",
                    ).classes("w-full")
                    self._target_fps_slider = (
                        ui.slider(min=5, max=60, step=5, value=self.config.target_fps)
                        .props("label")
                        .classes("w-full")
                    )
                    ui.label().bind_text_from(
                        self._target_fps_slider, "value",
                        backward=lambda v: f"Target FPS: {v:.0f}",
                    )

                with ui.card().classes("w-full"):
                    ui.label("Status").classes("text-subtitle1")
                    self._face_status = ui.label("Face: ⬤ Not detected")
                    self._fps_label = ui.label("FPS: --")
                    self._pos_label = ui.label("Pos: (--, --)")

                with ui.row().classes("w-full gap-2"):
                    self._start_button = ui.button(
                        "▶ Start",
                        on_click=self._start_tracking,
                    ).classes("flex-1").props("color=green")
                    self._stop_button = ui.button(
                        "■ Stop",
                        on_click=self._stop_tracking,
                    ).classes("flex-1").props("color=red")
                    self._stop_button.disable()

    async def _connect_to_obs(self):
        log.info("Connecting to OBS...")
        self._connect_button.disable()
        self._connect_button.text = "Connecting..."

        import asyncio
        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(None, self.obs.connect)

        if success:
            self._connect_button.text = "✓ Connected"
            self._connect_button.props("color=green")
            self._obs_status.set_text(
                f"OBS: ⬤ Connected | Canvas: {self.obs.canvas_width}×{self.obs.canvas_height}"
            )
            self._canvas_info.set_text(
                f"Canvas: {self.obs.canvas_width}×{self.obs.canvas_height}"
            )
            self._obs_help.set_visibility(False)
            await self._populate_scenes()
            ui.notify("Connected to OBS", type="positive")
        else:
            log.error("Failed to connect to OBS")
            self._connect_button.text = "Connect OBS"
            self._connect_button.enable()
            self._connect_button.props("color=None")
            self._obs_status.set_text("OBS: ⬤ Connection failed")
            self._obs_help.set_visibility(True)
            ui.notify(
                "Failed to connect. If OBS has authentication enabled, "
                "set password in Settings page. "
                "Or disable it: OBS → Tools → WebSocket Server Settings",
                type="negative",
                timeout=8000,
            )

    async def _populate_scenes(self):
        import asyncio
        loop = asyncio.get_running_loop()
        scenes = await loop.run_in_executor(None, self.obs.get_scenes)
        options = {s.name: s.name for s in scenes}
        self._scene_select.options = options
        self._scene_select.update()

        log.info("Populated %d scenes", len(options))

        if self.config.scene_name and self.config.scene_name in options:
            self._scene_select.value = self.config.scene_name
            await self._on_scene_change_impl(self.config.scene_name)

    async def _on_scene_change(self):
        scene_name = self._scene_select.value
        if scene_name:
            self.config.scene_name = scene_name
            await self._on_scene_change_impl(scene_name)

    async def _on_scene_change_impl(self, scene_name: str):
        import asyncio
        loop = asyncio.get_running_loop()
        items = await loop.run_in_executor(None, self.obs.get_scene_items, scene_name)

        source_names = [item.name for item in items]
        source_options = {name: name for name in source_names}

        self._timer_select.options = source_options
        self._camera_select.options = source_options
        self._timer_select.update()
        self._camera_select.update()

        if self.config.timer_source_name in source_options:
            self._timer_select.value = self.config.timer_source_name
        if self.config.camera_source_name in source_options:
            self._camera_select.value = self.config.camera_source_name

        log.debug(
            "Scene '%s': %d sources available",
            scene_name, len(source_options),
        )

    def _on_timer_change(self):
        self.config.timer_source_name = self._timer_select.value or ""

    def _on_camera_change(self):
        self.config.camera_source_name = self._camera_select.value or ""

    def _on_device_camera_change(self):
        val = self._device_camera_select.value
        self.config.camera_index = int(val) if val is not None else 0

    def _populate_camera_devices(self):
        devices = list_cameras()
        if devices:
            self._device_camera_select.options = devices
            self._device_camera_select.update()
            key = str(self.config.camera_index)
            if key in devices:
                self._device_camera_select.value = key
            log.info("Found %d capture devices", len(devices))
        else:
            self._device_camera_select.options = {"-1": "No cameras found"}
            self._device_camera_select.update()

    def _start_tracking(self):
        if not self.obs.connected:
            ui.notify("Connect to OBS first", type="warning")
            log.warning("Start tracking blocked: not connected to OBS")
            return
        if not self.config.timer_source_name:
            ui.notify("Select a timer widget source", type="warning")
            log.warning("Start tracking blocked: no timer source selected")
            return
        if not self.config.camera_source_name:
            ui.notify("Select a webcam source", type="warning")
            log.warning("Start tracking blocked: no camera source selected")
            return

        self.config.smoothing_alpha = self._smoothing_slider.value
        self.config.rotation_enabled = self._rotation_checkbox.value
        self.config.offset_y = int(self._offset_input.value)
        self.config.target_fps = float(self._target_fps_slider.value)

        log.info(
            "Starting tracking: scene='%s' timer='%s' camera='%s' cam_idx=%d alpha=%.2f rotation=%s offset=%d fps=%.0f",
            self.config.scene_name,
            self.config.timer_source_name,
            self.config.camera_source_name,
            self.config.camera_index,
            self.config.smoothing_alpha,
            self.config.rotation_enabled,
            self.config.offset_y,
            self.config.target_fps,
        )

        self._save_config()
        self.tracker.configure(self.config)

        try:
            self.tracker.start()
        except RuntimeError as e:
            log.error("Failed to start tracker: %s", e)
            ui.notify(str(e), type="negative")
            return

        self._start_button.disable()
        self._stop_button.enable()
        self._scene_select.disable()
        self._timer_select.disable()
        self._camera_select.disable()
        self._device_camera_select.disable()
        self._smoothing_slider.disable()
        self._rotation_checkbox.disable()
        self._offset_input.disable()
        self._target_fps_slider.disable()

        ui.notify("Tracking started", type="positive")

    def _stop_tracking(self):
        log.info("Stopping tracking")
        self.tracker.stop()

        self._start_button.enable()
        self._stop_button.disable()
        self._scene_select.enable()
        self._timer_select.enable()
        self._camera_select.enable()
        self._device_camera_select.enable()
        self._smoothing_slider.enable()
        self._rotation_checkbox.enable()
        self._offset_input.enable()
        self._target_fps_slider.enable()

        self._face_status.set_text("Face: ⬤ Not detected")
        self._fps_label.set_text("FPS: --")
        self._pos_label.set_text("Pos: (--, --)")

        ui.run_javascript("""
            var c = document.getElementById('preview-canvas');
            if (c) { c.width = 1; c.height = 1; }
        """)

        ui.notify("Tracking stopped", type="warning")

    def _update_preview(self):
        if not self.tracker.is_running:
            return
        if self._preview_html is None:
            return

        frame = self.tracker.latest_frame
        if frame is None or frame is self._last_preview_frame:
            return
        self._last_preview_frame = frame

        ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            return

        b64 = base64.b64encode(buf).decode()
        src = f"data:image/jpeg;base64,{b64}"

        ui.run_javascript(f"""
            var c = document.getElementById('preview-canvas');
            if (!c) return;
            var img = new Image();
            img.onload = function() {{
                c.width = img.width;
                c.height = img.height;
                c.getContext('2d').drawImage(img, 0, 0);
            }};
            img.src = '{src}';
        """)

    def _update_status(self):
        if not self.tracker.is_running:
            return

        if self._face_status:
            if self.tracker.face_detected:
                self._face_status.set_text("Face: ⬤ Detected")
            else:
                self._face_status.set_text("Face: ⬤ Not detected")

        if self._fps_label:
            self._fps_label.set_text(f"FPS: {self.tracker.fps:.1f}")

        if self._pos_label:
            forehead = self.tracker.latest_forehead
            if forehead:
                self._pos_label.set_text(
                    f"Pos: ({forehead.x:.3f}, {forehead.y:.3f})"
                )

    def run(self, host: str = "127.0.0.1", port: int = 8080, show: bool = True):
        log.info("Starting NiceGUI server on %s:%s", host, port)

        if getattr(sys, "frozen", False):
            icon_dir = Path(sys._MEIPASS)
        else:
            icon_dir = Path(__file__).resolve().parent.parent

        icon_path = icon_dir / "icon.png"
        favicon = "🎯"
        if icon_path.exists():
            favicon = str(icon_path)

        ui.run(
            host=host,
            port=port,
            title="MisterTimer",
            reload=False,
            show=show,
            favicon=favicon,
        )
