import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: PIL not installed. Run: uv sync")
    sys.exit(1)

ICON_PNG = Path(__file__).resolve().parent.parent / "icon.png"
ICON_ICO = Path(__file__).resolve().parent.parent / "icon.ico"

if not ICON_PNG.exists():
    print(f"ERROR: {ICON_PNG} not found")
    sys.exit(1)

img = Image.open(ICON_PNG)
img.save(
    ICON_ICO,
    format="ICO",
    sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
)
print(f"OK: {ICON_ICO} ({ICON_ICO.stat().st_size} bytes)")
