import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
)
MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "face_landmarker.task"


@dataclass
class ForeheadData:
    x: float
    y: float
    roll: float
    pitch: float
    yaw: float
    frame_width: int
    frame_height: int
    frame: np.ndarray


class FaceDetector:
    FOREHEAD_TOP = 10
    GLABELLA = 151
    LEFT_EYE_OUTER = 33
    LEFT_EYE_INNER = 133
    RIGHT_EYE_OUTER = 263
    RIGHT_EYE_INNER = 362
    NOSE_TIP = 1
    CHIN = 152

    FACE_OVAL = [
        10, 109, 67, 103, 54, 21, 162, 127, 234, 93, 132,
        58, 172, 136, 150, 149, 176, 148, 152, 377, 400,
        378, 379, 365, 397, 288, 361, 323, 454, 356, 389,
        251, 284, 332, 297, 338, 10,
    ]
    LEFT_EYE_CONTOUR = [33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7]
    RIGHT_EYE_CONTOUR = [263, 466, 388, 387, 386, 385, 384, 398, 362, 382, 381, 380, 374, 373, 390, 249]
    LIPS_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]
    LEFT_EYEBROW = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
    RIGHT_EYEBROW = [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]
    NOSE_BRIDGE = [6, 197, 195, 5, 4, 1]
    NOSE_BOTTOM = [98, 327, 2, 97, 248, 327]

    def __init__(self, max_faces: int = 1):
        model_path = self._ensure_model()
        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=max_faces,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)
        self._frame_timestamp = 0

    def _ensure_model(self) -> Path:
        if getattr(sys, "frozen", False):
            bundled = Path(sys._MEIPASS) / "models" / "face_landmarker.task"
            if bundled.exists():
                return bundled

        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not MODEL_PATH.exists():
            print(f"Downloading face landmarker model to {MODEL_PATH}...")
            try:
                urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
                print("Model downloaded.")
            except Exception as e:
                raise RuntimeError(
                    f"Failed to download model from {MODEL_URL}: {e}. "
                    f"Try downloading manually to {MODEL_PATH}"
                )
        return MODEL_PATH

    def detect(self, frame: np.ndarray) -> ForeheadData | None:
        frame_height, frame_width = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        self._frame_timestamp += 33
        result = self.landmarker.detect_for_video(mp_image, self._frame_timestamp)

        if not result.face_landmarks:
            return None

        landmarks = result.face_landmarks[0]

        fx = self._forehead_x(landmarks, frame_width)
        fy = self._forehead_y(landmarks, frame_height)

        roll, pitch, yaw = self._calc_head_pose(landmarks)

        self._draw_debug(frame, landmarks, fx, fy, roll, pitch, yaw)

        return ForeheadData(
            x=fx / frame_width,
            y=fy / frame_height,
            roll=roll,
            pitch=pitch,
            yaw=yaw,
            frame_width=frame_width,
            frame_height=frame_height,
            frame=frame,
        )

    def _forehead_x(self, landmarks, frame_width: int) -> float:
        x_top = landmarks[self.FOREHEAD_TOP].x * frame_width
        x_glabella = landmarks[self.GLABELLA].x * frame_width
        return (x_top + x_glabella) / 2.0

    def _forehead_y(self, landmarks, frame_height: int) -> float:
        y_top = landmarks[self.FOREHEAD_TOP].y * frame_height
        y_glabella = landmarks[self.GLABELLA].y * frame_height
        return (y_top + y_glabella) / 2.0

    def _calc_head_pose(self, landmarks) -> tuple[float, float, float]:
        left_eye_x = (landmarks[self.LEFT_EYE_OUTER].x + landmarks[self.LEFT_EYE_INNER].x) / 2
        left_eye_y = (landmarks[self.LEFT_EYE_OUTER].y + landmarks[self.LEFT_EYE_INNER].y) / 2
        right_eye_x = (landmarks[self.RIGHT_EYE_OUTER].x + landmarks[self.RIGHT_EYE_INNER].x) / 2
        right_eye_y = (landmarks[self.RIGHT_EYE_OUTER].y + landmarks[self.RIGHT_EYE_INNER].y) / 2

        dx = right_eye_x - left_eye_x
        dy = right_eye_y - left_eye_y
        roll = np.degrees(np.arctan2(dy, dx))

        eye_center_x = (left_eye_x + right_eye_x) / 2
        eye_center_y = (left_eye_y + right_eye_y) / 2
        nose_x = landmarks[self.NOSE_TIP].x
        nose_y = landmarks[self.NOSE_TIP].y

        eye_dist = np.hypot(dx, dy)
        if eye_dist > 0.001:
            yaw = np.degrees(np.arctan2(nose_x - eye_center_x, eye_dist)) * 2.0
            pitch = np.degrees(np.arctan2(nose_y - eye_center_y, eye_dist)) * 2.0
        else:
            yaw, pitch = 0.0, 0.0

        return (roll, pitch, yaw)

    def _draw_debug(self, frame, landmarks, fx, fy, roll, pitch, yaw):
        h, w = frame.shape[:2]
        fx_int, fy_int = int(fx), int(fy)

        self._draw_face_mesh(frame, landmarks, w, h)
        self._draw_eyes(frame, landmarks, w, h)

        cv2.line(frame, (fx_int, fy_int - 25), (fx_int, fy_int + 25), (0, 255, 0), 2)
        cv2.line(frame, (fx_int - 25, fy_int), (fx_int + 25, fy_int), (0, 255, 0), 2)

        roll_rad = np.radians(-roll)
        r_len = 60
        cv2.line(frame, (fx_int, fy_int),
                 (fx_int + int(r_len * np.cos(roll_rad)), fy_int + int(r_len * np.sin(roll_rad))),
                 (255, 80, 80), 3)

        self._draw_angle_arc(frame, fx_int, fy_int, roll_rad)

        nose_x = int(landmarks[self.NOSE_TIP].x * w)
        nose_y = int(landmarks[self.NOSE_TIP].y * h)
        cv2.circle(frame, (nose_x, nose_y), 4, (0, 0, 255), -1)

        left_eye_cx = int((landmarks[self.LEFT_EYE_OUTER].x + landmarks[self.LEFT_EYE_INNER].x) / 2 * w)
        left_eye_cy = int((landmarks[self.LEFT_EYE_OUTER].y + landmarks[self.LEFT_EYE_INNER].y) / 2 * h)
        right_eye_cx = int((landmarks[self.RIGHT_EYE_OUTER].x + landmarks[self.RIGHT_EYE_INNER].x) / 2 * w)
        right_eye_cy = int((landmarks[self.RIGHT_EYE_OUTER].y + landmarks[self.RIGHT_EYE_INNER].y) / 2 * h)
        eye_cx = int((left_eye_cx + right_eye_cx) / 2)
        eye_cy = int((left_eye_cy + right_eye_cy) / 2)

        cv2.line(frame, (left_eye_cx, left_eye_cy), (right_eye_cx, right_eye_cy), (0, 255, 255), 2)
        cv2.circle(frame, (left_eye_cx, left_eye_cy), 3, (255, 255, 255), -1)
        cv2.circle(frame, (right_eye_cx, right_eye_cy), 3, (255, 255, 255), -1)

        cv2.arrowedLine(frame, (eye_cx, eye_cy), (nose_x, nose_y), (0, 140, 255), 1, tipLength=0.3)

        texts = [
            (f"Roll: {roll:+.1f} deg", (10, 25), (255, 80, 80)),
            (f"Pitch: {pitch:+.1f} deg", (10, 50), (0, 140, 255)),
            (f"Yaw: {yaw:+.1f} deg", (10, 75), (0, 255, 255)),
            (f"Forehead: ({fx/w:.3f}, {fy/h:.3f})", (10, 100), (0, 255, 0)),
        ]
        for text, pos, color in texts:
            cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

        self._draw_widget_preview(frame, fx_int, fy_int, roll_rad)

    def _draw_face_mesh(self, frame, landmarks, w, h):
        overlay = frame.copy()
        for indices, color in [
            (self.FACE_OVAL, (100, 100, 255)),
            (self.LEFT_EYEBROW, (255, 200, 150)),
            (self.RIGHT_EYEBROW, (255, 200, 150)),
            (self.LEFT_EYE_CONTOUR, (255, 255, 100)),
            (self.RIGHT_EYE_CONTOUR, (255, 255, 100)),
            (self.LIPS_OUTER, (150, 150, 255)),
            (self.NOSE_BRIDGE, (200, 200, 255)),
            (self.NOSE_BOTTOM, (200, 200, 255)),
        ]:
            pts = [(int(landmarks[i].x * w), int(landmarks[i].y * h)) for i in indices]
            for i in range(len(pts) - 1):
                cv2.line(overlay, pts[i], pts[i + 1], color, 1)
            if len(pts) > 2:
                cv2.line(overlay, pts[-1], pts[0], color, 1)

        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

    def _draw_eyes(self, frame, landmarks, w, h):
        for contour in [self.LEFT_EYE_CONTOUR, self.RIGHT_EYE_CONTOUR]:
            pts = [(int(landmarks[i].x * w), int(landmarks[i].y * h)) for i in contour]
            for i in range(len(pts) - 1):
                cv2.line(frame, pts[i], pts[i + 1], (100, 255, 255), 1)

    def _draw_angle_arc(self, frame, cx, cy, roll_rad):
        radius = 35
        start_angle = int(np.degrees(-roll_rad - 0.8))
        end_angle = int(np.degrees(-roll_rad + 0.8))
        color = (255, 80, 80)
        cv2.ellipse(frame, (cx, cy), (radius, radius), 0,
                    start_angle, end_angle, color, 2)
        end_x = int(cx + radius * np.cos(-roll_rad + 0.8))
        end_y = int(cy + radius * np.sin(-roll_rad + 0.8))
        cv2.circle(frame, (end_x, end_y), 3, color, -1)

    def _draw_widget_preview(self, frame, fx, fy, roll_rad):
        w, h = 80, 24
        pts = np.array([
            [-w/2, -h/2], [w/2, -h/2], [w/2, h/2], [-w/2, h/2]
        ])
        cos_a, sin_a = np.cos(roll_rad), np.sin(roll_rad)
        rot = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
        pts = (rot @ pts.T).T + np.array([fx, fy])
        pts = pts.astype(np.int32)
        cv2.polylines(frame, [pts], True, (0, 255, 0), 1)
        cv2.putText(frame, "TIMER", (int(fx - w/2 + 4), int(fy + 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1, cv2.LINE_AA)

    def release(self):
        if self.landmarker is not None:
            self.landmarker.close()
