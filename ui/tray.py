import sys
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw


def setup_tray():
    if not getattr(sys, "frozen", False):
        return

    icon = _load_icon()
    menu = pystray.Menu(
        pystray.MenuItem("Open", _open_browser, default=True),
        pystray.MenuItem("Quit", _quit),
    )
    tray = pystray.Icon("MisterTimer", icon, "MisterTimer", menu)
    tray.run_detached()


def _load_icon():
    paths = [
        Path(sys._MEIPASS) / "icon.png",
        Path(sys._MEIPASS) / "icon.ico",
        Path("icon.png"),
        Path("icon.ico"),
    ]
    for p in paths:
        if p.exists():
            return Image.open(p)

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([8, 8, 56, 56], fill=(0, 200, 100))
    draw.ellipse([20, 20, 44, 44], fill=(255, 255, 255, 100))
    return img


def _open_browser():
    webbrowser.open("http://localhost:8080")


def _quit():
    import os
    os._exit(0)
