import base64
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from src.coordinate_mapper import CoordinateMapper
from src.face_detector import FaceDetector, ForeheadData
from src.obs_connector import OBSConnector, SceneItemTransform
from src.smoother import Smoother


@dataclass
class TrackerConfig:
    scene_name: str = ""
    timer_source_name: str = ""
    camera_source_name: str = ""
    smoothing_alpha: float = 0.3
    rotation_enabled: bool = True
    offset_y: int = 20


class HeadTracker:
    def __init__(self, obs: OBSConnector):
        self.obs = obs
        self.config = TrackerConfig()
        self._detector: FaceDetector | None = None
        self._mapper: CoordinateMapper | None = None
        self._smoother: Smoother | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._done_event = threading.Event()
        self._running = False
        self._face_detected = False
        self._latest_frame: np.ndarray | None = None
        self._latest_forehead: ForeheadData | None = None
        self._fps = 0.0
        self._lock = threading.Lock()
        self._obs_lock = threading.Lock()
        self._timer_item_id: int | None = None
        self._webcam_item_id: int | None = None
        self._webcam_transform_cache = None
        self._webcam_transform_cache_scene = ""
        self._webcam_transform_cache_item_id = 0
        self._current_rotation: float = 0.0
        self._base_scale_x: float | None = None
        self._base_scale_y: float | None = None
        self._saved_transform: SceneItemTransform | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def face_detected(self) -> bool:
        return self._face_detected

    @property
    def latest_frame(self) -> np.ndarray | None:
        with self._lock:
            return self._latest_frame

    @property
    def latest_forehead(self) -> ForeheadData | None:
        with self._lock:
            return self._latest_forehead

    @property
    def fps(self) -> float:
        return self._fps

    def configure(self, config: TrackerConfig):
        self.config = config

    def start(self):
        if self._running:
            return

        self._stop_event.clear()
        self._done_event.clear()
        self._resolve_source_ids()

        if self._timer_item_id is None:
            raise RuntimeError(
                f"Source '{self.config.timer_source_name}' not found"
            )

        self._detector = FaceDetector()
        self._mapper = CoordinateMapper(
            canvas_width=self.obs.canvas_width,
            canvas_height=self.obs.canvas_height,
        )
        self._smoother = Smoother(alpha=self.config.smoothing_alpha)
        self._webcam_transform_cache = None
        self._current_rotation = 0.0
        self._base_scale_x = None
        self._base_scale_y = None
        self._saved_transform = None

        with self._obs_lock:
            self._saved_transform = self.obs.get_scene_item_transform(
                self.config.scene_name, self._timer_item_id
            )

        self._thread = threading.Thread(target=self._track_loop, daemon=True)
        self._thread.start()
        self._running = True

    def stop(self):
        self._stop_event.set()
        self._running = False
        self._done_event.wait(timeout=0.5)

        if self._saved_transform is not None and self._timer_item_id is not None:
            t = self._saved_transform
            with self._obs_lock:
                self.obs.set_scene_item_transform(
                    self.config.scene_name,
                    self._timer_item_id,
                    pos_x=t.pos_x,
                    pos_y=t.pos_y,
                    rotation=t.rotation,
                    scale_x=t.scale_x,
                    scale_y=t.scale_y,
                )

        self._webcam_transform_cache = None

    def _resolve_source_ids(self):
        with self._obs_lock:
            self._timer_item_id = self.obs.get_scene_item_id_by_name(
                self.config.scene_name, self.config.timer_source_name
            )
            self._webcam_item_id = self.obs.get_scene_item_id_by_name(
                self.config.scene_name, self.config.camera_source_name
            )

    def _get_cached_webcam_transform(self) -> SceneItemTransform | None:
        if self._webcam_item_id is None:
            return None

        if (self._webcam_transform_cache
                and self._webcam_transform_cache_scene == self.config.scene_name
                and self._webcam_transform_cache_item_id == self._webcam_item_id):
            return self._webcam_transform_cache

        with self._obs_lock:
            transform = self.obs.get_scene_item_transform(
                self.config.scene_name, self._webcam_item_id
            )

        if transform is not None:
            self._webcam_transform_cache = transform
            self._webcam_transform_cache_scene = self.config.scene_name
            self._webcam_transform_cache_item_id = self._webcam_item_id

        return transform

    def _fetch_frame(self) -> np.ndarray | None:
        with self._obs_lock:
            b64_str = self.obs.get_source_screenshot(
                self.config.camera_source_name
            )
        if not b64_str:
            return None
        try:
            b64_str = b64_str.partition(",")[-1] if "," in b64_str else b64_str
            data = base64.b64decode(b64_str)
            arr = np.frombuffer(data, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return frame
        except Exception:
            return None

    def _track_loop(self):
        frame_count = 0
        last_fps_time = time.time()
        last_transform_refresh = time.time()

        while not self._stop_event.is_set():
            if self._detector is None or self._mapper is None or self._smoother is None:
                break

            frame = self._fetch_frame()
            if frame is None:
                time.sleep(0.002)
                continue

            forehead_data = self._detector.detect(frame)

            with self._lock:
                if forehead_data is not None:
                    self._latest_frame = forehead_data.frame.copy()
                    self._latest_forehead = forehead_data
                    self._face_detected = True

                    transform = None
                    if time.time() - last_transform_refresh > 5.0:
                        transform = self._get_cached_webcam_transform()
                        last_transform_refresh = time.time()
                    elif self._webcam_transform_cache is None:
                        transform = self._get_cached_webcam_transform()
                    else:
                        transform = self._webcam_transform_cache

                    if transform:
                        self._mapper.update_webcam_transform(transform)

                    canvas_coords = self._mapper.map_to_canvas(
                        forehead_data.x,
                        forehead_data.y,
                        forehead_data.frame_width,
                        forehead_data.frame_height,
                    )

                    if canvas_coords:
                        canvas_x, canvas_y = canvas_coords
                        canvas_y -= self.config.offset_y

                        canvas_x, canvas_y = self._smoother.smooth_position(canvas_x, canvas_y)

                        if self.config.rotation_enabled:
                            self._current_rotation = self._smoother.smooth_angle(forehead_data.roll)

                        perspective_sx = 1.0 - abs(forehead_data.yaw) * 0.005
                        perspective_sy = 1.0 - abs(forehead_data.pitch) * 0.005

                        if self._timer_item_id is not None:
                            if self._base_scale_x is None:
                                with self._obs_lock:
                                    base = self.obs.get_scene_item_transform(
                                        self.config.scene_name, self._timer_item_id
                                    )
                                if base:
                                    self._base_scale_x = base.scale_x
                                    self._base_scale_y = base.scale_y

                            sx = (self._base_scale_x or 1.0) * perspective_sx
                            sy = (self._base_scale_y or 1.0) * perspective_sy

                            with self._obs_lock:
                                self.obs.set_scene_item_transform(
                                    self.config.scene_name,
                                    self._timer_item_id,
                                    canvas_x,
                                    canvas_y,
                                    rotation=self._current_rotation,
                                    scale_x=sx,
                                    scale_y=sy,
                                )
                else:
                    self._face_detected = False

            frame_count += 1
            now = time.time()
            elapsed = now - last_fps_time
            if elapsed >= 1.0:
                self._fps = frame_count / elapsed
                frame_count = 0
                last_fps_time = now

            time.sleep(0.002)

        if self._detector:
            self._detector.release()
            self._detector = None

        self._done_event.set()
