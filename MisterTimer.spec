# -*- mode: python ; coding: utf-8 -*-
"""
MisterTimer — size-optimised PyInstaller spec.

Ключевые отличия от исходного спека:
  1. libmediapipe.dll (43 МБ) кладётся ОДИН раз, а не 2-4 раза.
  2. Из nicegui/elements/lib берутся только реально используемые JS-библиотеки
     (по умолчанию — ни одной: mermaid/plotly/echarts/aggrid/three/... не нужны).
  3. Выкинуты matplotlib, sounddevice, tkinter, тесты и прочий мусор.
  4. Выкинут opencv_videoio_ffmpeg*.dll (31 МБ) — видео-I/O в проекте не используется.
  5. Иконка ужимается до 256x256 вместо 2.5 МБ PNG.
  6. optimize=2 — байткод без докстрингов.
  7. EXCLUDE_CV2: после переписывания рисовалки на Pillow ставим True → минус ~115 МБ.
"""

from pathlib import Path
import mediapipe, nicegui

# ---------------------------------------------------------------- настройки

# Поставить True ПОСЛЕ того, как cv2.* в src/face_detector.py, src/head_tracker.py
# и ui/app.py заменён на Pillow. mediapipe 1.0.0 сам по себе cv2 НЕ импортирует
# (проверено: cv2 нужен только в mediapipe/tasks/python/vision/drawing_utils.py,
# который проект не использует).
EXCLUDE_CV2 = False

# JS-библиотеки NiceGUI, которые реально нужны приложению.
# Проект использует только label/button/select/card/row/column/number/html/
# timer/slider/input/checkbox/link/header/notify — ничему из lib/ они не нужны.
# Если добавишь ui.plotly / ui.echart / ui.aggrid / ui.markdown с mermaid —
# впиши сюда имя папки из nicegui/elements/lib/.
KEEP_NICEGUI_LIBS: set[str] = set()

# ------------------------------------------------------------------- пути

_mp_dir = Path(mediapipe.__file__).parent
_ng_dir = Path(nicegui.__file__).parent
_here = Path(SPECPATH)

datas = [("config.example.json", ".")]

# ------------------------------------------------------- NiceGUI (~65 -> ~6 МБ)

datas.append((str(_ng_dir / "static"), "nicegui/static"))
datas.append((str(_ng_dir / "templates"), "nicegui/templates"))

_ng_elements = _ng_dir / "elements"
_skipped_libs = []
for _p in _ng_elements.rglob("*"):
    if not _p.is_file():
        continue
    _rel = _p.relative_to(_ng_elements)
    if _rel.parts and _rel.parts[0] == "lib":
        _lib = _rel.parts[1] if len(_rel.parts) > 1 else None
        if _lib not in KEEP_NICEGUI_LIBS:
            _skipped_libs.append(_lib)
            continue
    datas.append((str(_p), str(Path("nicegui/elements") / _rel.parent)))
print(f"SPEC: nicegui — пропущено JS-библиотек: {len(set(_skipped_libs))} "
      f"({', '.join(sorted(set(x for x in _skipped_libs if x)))})")

# ------------------------------------------------------------- иконка (2.5 -> ~0.1 МБ)

_icon_png_src = _here / "icon.png"
_icon_png_small = _here / "icon_small.png"
_icon_ico = _here / "icon.ico"

if _icon_png_src.exists():
    try:
        from PIL import Image

        _img = Image.open(_icon_png_src).convert("RGBA")
        _img.resize((256, 256), Image.LANCZOS).save(
            _icon_png_small, format="PNG", optimize=True
        )
        _img.save(
            _icon_ico,
            format="ICO",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
        )
        print(f"SPEC: icon_small.png = {_icon_png_small.stat().st_size // 1024} KB, "
              f"icon.ico = {_icon_ico.stat().st_size // 1024} KB")
    except Exception as e:
        print(f"SPEC: icon generation failed: {e}")

# Внутри бандла оба файла называются icon.png / icon.ico — код в ui/tray.py и
# ui/app.py менять не нужно.
if _icon_png_small.exists():
    datas.append((str(_icon_png_small), "."))
elif _icon_png_src.exists():
    datas.append((str(_icon_png_src), "."))
if _icon_ico.exists():
    datas.append((str(_icon_ico), "."))

# ------------------------------------------------- mediapipe (90 -> 45 МБ)

# Исходный спек добавлял libmediapipe.dll в binaries ДВАЖДЫ (в mediapipe/tasks/c
# и в корень) и ещё дважды в datas → 2 физические копии по 43 МБ.
# runtime-хук уже делает add_dll_directory(_MEIPASS/mediapipe/tasks/c),
# поэтому достаточно одной копии на «родном» месте.
_mp_binaries = []
_mp_c = _mp_dir / "tasks" / "c"
if _mp_c.is_dir():
    for f in sorted(_mp_c.iterdir()):
        if f.suffix.lower() in (".dll", ".so", ".dylib", ".pyd"):
            _mp_binaries.append((str(f), "mediapipe/tasks/c"))
            print(f"SPEC: mediapipe binary {f.name} "
                  f"({f.stat().st_size / 1e6:.1f} MB) -> mediapipe/tasks/c")
if not _mp_binaries:
    print("SPEC: WARNING — не найдено ни одной нативной библиотеки mediapipe!")

# ------------------------------------------------------------------ модель

_model_file = _here / "models" / "face_landmarker.task"
if _model_file.exists():
    datas.append((str(_model_file), "models"))
else:
    print("SPEC: WARNING — models/face_landmarker.task отсутствует")

# ----------------------------------------------------------------- excludes

excludes = [
    # тянется как зависимость mediapipe, но не импортируется
    "matplotlib", "mpl_toolkits", "pylab",
    "sounddevice", "_sounddevice_data",
    # научный стек, которого тут нет и быть не должно
    "scipy", "pandas", "sympy", "jax", "jaxlib", "torch", "tensorflow",
    # GUI-тулкиты
    "tkinter", "Tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
    "PIL.ImageQt", "PIL.ImageTk", "PIL.ImageShow", "PIL._avif", "PIL.AvifImagePlugin",
    # dev / repl
    "IPython", "jupyter", "notebook", "pytest", "_pytest",
    "unittest", "doctest", "pydoc", "pydoc_data", "test", "tests",
    "distutils", "setuptools", "pkg_resources",
    "numpy.f2py", "numpy.testing", "numpy.distutils",
    # uvicorn[standard]-экстры: нужны только для --reload, на Windows часть
    # вообще не ставится
    "uvloop", "watchfiles", "httptools",
    # linux/mac-специфика pystray
    "Xlib", "python-xlib", "gi", "AppKit", "Foundation", "objc",
]

if EXCLUDE_CV2:
    excludes += ["cv2", "opencv"]

hiddenimports = [
    "mediapipe",
    "mediapipe.tasks",
    "mediapipe.tasks.python",
    "mediapipe.tasks.python.vision",
    "nicegui",
    "obsws_python",
    "numpy",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "pystray",
    "pystray._win32",
    "ui.tray",
]
if not EXCLUDE_CV2:
    hiddenimports.append("cv2")

# ------------------------------------------------------------------ Analysis

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=_mp_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["hooks/runtime.py"],
    excludes=excludes,
    noarchive=False,
    optimize=2,
)

# ------------------------------- пост-фильтр: выкидываем крупный мёртвый груз

_DROP_PATTERNS = (
    "opencv_videoio_ffmpeg",   # 31 МБ, видео-I/O не используется
    "pil/_avif",               # 8 МБ, AVIF не нужен
    "mediapipe/tasks/python/test",
    "share/doc",
    "/tests/",
)


def _prune(entries, label):
    kept, dropped, saved = [], 0, 0
    for entry in entries:
        dest = entry[0].replace("\\", "/").lower()
        if any(p in dest for p in _DROP_PATTERNS):
            dropped += 1
            try:
                saved += Path(entry[1]).stat().st_size
            except OSError:
                pass
            continue
        kept.append(entry)
    if dropped:
        print(f"SPEC: {label} — выкинуто {dropped} файлов, ~{saved / 1e6:.1f} MB")
    return kept


a.binaries = _prune(a.binaries, "binaries")
a.datas = _prune(a.datas, "datas")

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MisterTimer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX на раннере GitHub Actions не установлен, так что upx=True был no-op.
    # На cv2.pyd/libmediapipe.dll UPX к тому же регулярно ломает загрузку.
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_icon_ico) if _icon_ico.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MisterTimer",
)
