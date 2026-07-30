import logging
import cv2
import numpy as np

log = logging.getLogger(__name__)


def list_cameras() -> dict[str, str]:
    devices: dict[str, str] = {}
    for i in range(10):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            label = f"Camera {i}"
            backend_idx = int(cap.get(cv2.CAP_PROP_BACKEND))
            try:
                backend_name = cap.getBackendName()
            except Exception:
                backend_name = ""
            if backend_name:
                label += f" [{backend_name}]"
            devices[str(i)] = label
            log.debug("Found camera %s: %s", i, label)
        cap.release()
    return devices


class CameraCapture:
    def __init__(self, index: int = 0, width: int = 640, height: int = 360):
        self._cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, 30)
        log.info(
            "Camera %d opened: %s×%s",
            index,
            self._cap.get(cv2.CAP_PROP_FRAME_WIDTH),
            self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
        )

    def read(self) -> np.ndarray | None:
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None
        return frame

    def release(self):
        if self._cap:
            self._cap.release()
            log.info("Camera released")
