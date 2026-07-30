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

_icon_png = Path(SPECPATH) / "icon.png"
_icon_ico = Path(SPECPATH) / "icon.ico"

if _icon_png.exists():
    datas.append((str(_icon_png), "."))

if _icon_png.exists():
    try:
        from PIL import Image
        img = Image.open(_icon_png)
        img.save(
            _icon_ico, format="ICO",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
        )
        print(f"SPEC: generated {_icon_ico} ({_icon_ico.stat().st_size} bytes)")
    except Exception as e:
        print(f"SPEC: icon.ico generation failed: {e}")

if _icon_ico.exists():
    datas.append((str(_icon_ico), "."))
    print(f"SPEC: icon.ico ready, {_icon_ico.stat().st_size} bytes")
else:
    print("SPEC: WARNING — no icon.ico, EXE will use default icon")

_mp_bin = _mp_dir / "tasks" / "c"
_mp_binaries = []
_mp_dll = None
for candidate in [
    _mp_dir / "tasks" / "c",
    _mp_dir / "modules" / "face_landmarker",
]:
    if candidate.exists():
        for f in candidate.iterdir():
            if f.suffix in (".so", ".dll"):
                dest = str(f.relative_to(_mp_dir.parent))
                _mp_binaries.append((str(f), dest))
                _mp_binaries.append((str(f), "."))
                datas.append((str(f), dest))
                datas.append((str(f), "."))
                if not _mp_dll:
                    _mp_dll = f
        if _mp_dll:
            break

if not _mp_dll:
    for f in _mp_dir.rglob("*.dll"):
        dest = str(f.relative_to(_mp_dir.parent))
        _mp_binaries.append((str(f), dest))
        _mp_binaries.append((str(f), "."))
        datas.append((str(f), dest))
        datas.append((str(f), "."))
        break
    for f in _mp_dir.rglob("*.so"):
        dest = str(f.relative_to(_mp_dir.parent))
        _mp_binaries.append((str(f), dest))
        _mp_binaries.append((str(f), "."))
        datas.append((str(f), dest))
        datas.append((str(f), "."))
        break

_model_dir = Path(SPECPATH) / "models"
_model_file = _model_dir / "face_landmarker.task"
if _model_file.exists():
    datas.append((str(_model_file), "models"))

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=_mp_binaries,
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
        "pystray",
        "pystray._win32",
        "PIL.ImageDraw",
        "PIL.Image",
        "ui.tray",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["hooks/runtime.py"],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe_icon = "icon.ico" if _icon_ico.exists() else None
if exe_icon:
    print(f"SPEC: EXE icon set to {exe_icon}")
else:
    print("SPEC: EXE icon is None — default will be used")

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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['*.dll', '*.so'],
    name='MisterTimer',
)
