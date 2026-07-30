# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import mediapipe, nicegui

_mp_dir = Path(mediapipe.__file__).parent
_ng_dir = Path(nicegui.__file__).parent

datas = [
    ("config.example.json", "."),
    (str(_ng_dir / "static"), "nicegui/static"),
    (str(_ng_dir / "templates"), "nicegui/templates"),
    (str(_ng_dir / "elements"), "nicegui/elements"),
]

# bundle mediapipe .so/.dll
_mp_bin = _mp_dir / "tasks" / "c"
if _mp_bin.exists():
    for f in _mp_bin.iterdir():
        if f.suffix in (".so", ".dll"):
            datas.append((str(f), str(f.relative_to(_mp_dir.parent))))

# bundle model if cached
_model_dir = Path(SPECPATH) / "models"
_model_file = _model_dir / "face_landmarker.task"
if _model_file.exists():
    datas.append((str(_model_file), "models"))

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "mediapipe",
        "mediapipe.tasks",
        "mediapipe.tasks.python",
        "mediapipe.tasks.python.vision",
        "cv2",
        "nicegui",
        "nicegui.elements",
        "nicegui.static",
        "obsws_python",
        "numpy",
        "PIL",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MisterTimer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MisterTimer',
)
