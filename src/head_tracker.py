import base64
import logging
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from src.coordinate_mapper import CoordinateMapper
from src.face_detector import FaceDetector, ForeheadData
from src.obs_connector import OBSConnector, SceneItemTransform
from src.smoother import Smoother

log = logging.getLogger(__name__)


@dataclass
class TrackerConfig:
    scene_name: str = ""
    timer_source_name: str = ""
    camera_source_name: str = ""
    smoothing_alpha: float = 0.3
    rotation_enabled: bool = True
    offset_y: int = 20
    target_fps: float = 30.0


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

        log.info("Starting head tracker")

        self._stop_event.clear()
        self._done_event.clear()
        self._resolve_source_ids()

        if self._timer_item_id is None:
            raise RuntimeError(
                f"Source '{self.config.timer_source_name}' not found"
            )

        if self._webcam_item_id is None:
            log.warning(
                "Webcam source '%s' not found in scene '%s' — "
                "screenshot fetch may fail",
                self.config.camera_source_name,
                self.config.scene_name,
            )

        log.debug("Creating face detector")
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

        log.debug("Saving current timer widget transform")
        with self._obs_lock:
            self._saved_transform = self.obs.get_scene_item_transform(
                self.config.scene_name, self._timer_item_id
            )
            if self._saved_transform:
                log.debug(
                    "Saved transform: pos=(%.1f, %.1f) scale=(%.2f, %.2f) rot=%.1f",
                    self._saved_transform.pos_x,
                    self._saved_transform.pos_y,
                    self._saved_transform.scale_x,
                    self._saved_transform.scale_y,
                    self._saved_transform.rotation,
                )

        self._thread = threading.Thread(target=self._track_loop, daemon=True)
        self._thread.start()
        self._running = True
        log.info("Head tracker started — thread running")

    def stop(self):
        log.info("Stopping head tracker")
        self._stop_event.set()
        self._running = False
        self._done_event.wait(timeout=0.5)

        if self._saved_transform is not None and self._timer_item_id is not None:
            t = self._saved_transform
            log.debug("Restoring original timer widget transform")
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
        log.info("Head tracker stopped")

    def _resolve_source_ids(self):
        with self._obs_lock:
            self._timer_item_id = self.obs.get_scene_item_id_by_name(
                self.config.scene_name, self.config.timer_source_name
            )
            self._webcam_item_id = self.obs.get_scene_item_id_by_name(
                self.config.scene_name, self.config.camera_source_name
            )
        log.debug(
            "Resolved source IDs: timer=%s, webcam=%s",
            self._timer_item_id,
            self._webcam_item_id,
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
            if frame is None:
                log.debug("cv2.imdecode returned None")
            return frame
        except Exception:
            log.error("Failed to decode screenshot frame", exc_info=True)
            return None

    def _track_loop(self):
        frame_count = 0
        fps_interval_start = time.perf_counter()
        last_transform_refresh = time.perf_counter()
        last_keepalive = time.perf_counter()
        consecutive_failures = 0
        _no_face_logged = False

        log.info(
            "Tracking loop started — target FPS: %.0f",
            self.config.target_fps,
        )
        while not self._stop_event.is_set():
            if self._detector is None or self._mapper is None or self._smoother is None:
                break

            loop_start = time.perf_counter()

            frame = self._fetch_frame()
            if frame is None:
                consecutive_failures += 1
                if consecutive_failures == 1:
                    log.warning(
                        "Cannot fetch screenshot from source '%s' — "
                        "check OBS connection and camera source name",
                        self.config.camera_source_name,
                    )
                if consecutive_failures >= 10:
                    log.error(
                        "Screenshot fetch failed %d times consecutively — "
                        "stopping tracking loop",
                        consecutive_failures,
                    )
                    break
                time.sleep(0.5)
                continue
            consecutive_failures = 0

            forehead_data = self._detector.detect(frame)

            with self._lock:
                if forehead_data is not None:
                    if _no_face_logged:
                        log.info("Face detected")
                    _no_face_logged = False

                    self._latest_frame = forehead_data.frame
                    self._latest_forehead = forehead_data
                    self._face_detected = True

                    now = time.perf_counter()
                    if now - last_transform_refresh > 5.0:
                        transform = self._get_cached_webcam_transform()
                        last_transform_refresh = now
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
                        log.debug("canvas_coords is None — mapper returned no result")
                else:
                    if not _no_face_logged:
                        log.info("No face detected in frame — waiting for face")
                        _no_face_logged = True
                    self._face_detected = False

            frame_count += 1
            now = time.perf_counter()
            elapsed = now - fps_interval_start
            if elapsed >= 1.0:
                self._fps = frame_count / elapsed
                frame_count = 0
                fps_interval_start = now

            if now - last_keepalive >= 10.0:
                self.obs.ping()
                last_keepalive = now

            loop_elapsed = time.perf_counter() - loop_start
            frame_budget = 1.0 / self.config.target_fps
            if loop_elapsed < frame_budget:
                time.sleep(frame_budget - loop_elapsed)

        if self._detector:
            self._detector.release()
            self._detector = None

        log.debug("Tracking loop ended")
        self._done_event.set()
