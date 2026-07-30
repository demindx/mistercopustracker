import logging
import subprocess
import cv2
import numpy as np

log = logging.getLogger(__name__)


def _get_win_camera_names() -> dict[int, str]:
    names: dict[int, str] = {}
    try:
        proc = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_PnPEntity | Where-Object {"
                "$_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image'} |"
                "Select-Object Name | ForEach-Object { $_.Name }",
            ],
            capture_output=True, text=True, timeout=5,
        )
        for i, line in enumerate(proc.stdout.strip().splitlines()):
            name = line.strip()
            if name:
                names[i] = name
    except Exception:
        pass
    return names


def list_cameras() -> dict[str, str]:
    devices: dict[str, str] = {}
    win_names = _get_win_camera_names()

    for backend_id, backend_name in [
        (cv2.CAP_DSHOW, "DSHOW"),
        (cv2.CAP_MSMF, "MSMF"),
    ]:
        for i in range(20):
            key = str(i)
            if key in devices:
                continue
            cap = cv2.VideoCapture(i, backend_id)
            if cap.isOpened():
                cap.release()
                label = win_names.get(i, f"Camera {i}")
                label += f" [{backend_name}]"
                devices[key] = label
                log.debug("Found camera %s: %s", key, label)
            cap.release()

    if not devices:
        for i in range(20):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cap.release()
                key = str(i)
                label = f"Camera {i}"
                if i in win_names:
                    label = win_names[i]
                devices[key] = label
            cap.release()

    return devices


class CameraCapture:
    def __init__(self, index: int = 0, width: int = 640, height: int = 360):
        self._cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not self._cap.isOpened():
            self._cap.release()
            self._cap = cv2.VideoCapture(index)
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
