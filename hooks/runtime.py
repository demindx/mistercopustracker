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


class _DummyLoader:
    def create_module(self, spec):
        return types.ModuleType(spec.name)

    def exec_module(self, module):
        pass


class _MPDrawingBlocker:
    BLOCK = {
        "mediapipe.tasks.python.vision.drawing_utils",
        "mediapipe.tasks.python.vision.drawing_styles",
    }

    def find_spec(self, fullname, path, target=None):
        if fullname in self.BLOCK:
            return importlib.machinery.ModuleSpec(
                fullname,
                _DummyLoader(),
                is_package=False,
            )
        return None


import importlib.machinery
sys.meta_path.insert(0, _MPDrawingBlocker())
