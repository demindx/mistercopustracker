import os
import sys
import types

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


class _MPDrawingBlocker:
    BLOCK = {
        "mediapipe.tasks.python.vision.drawing_utils",
        "mediapipe.tasks.python.vision.drawing_styles",
    }

    def find_module(self, fullname, path=None):
        if fullname in self.BLOCK:
            return self
        return None

    def load_module(self, fullname):
        mod = types.ModuleType(fullname)
        sys.modules[fullname] = mod
        return mod


sys.meta_path.insert(0, _MPDrawingBlocker())
