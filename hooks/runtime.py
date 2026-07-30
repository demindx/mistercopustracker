import os
import sys

if getattr(sys, "frozen", False):
    _mp_dll_dir = os.path.join(sys._MEIPASS, "mediapipe", "tasks", "c")
    if os.path.isdir(_mp_dll_dir):
        try:
            os.add_dll_directory(_mp_dll_dir)
        except Exception:
            pass
    try:
        os.add_dll_directory(str(sys._MEIPASS))
    except Exception:
        pass
