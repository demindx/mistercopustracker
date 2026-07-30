#!/usr/bin/env bash
# Build standalone executable with PyInstaller
# Run this on the target OS (Windows for .exe, Linux for binary, macOS for .app)

set -e

echo "=== Downloading MediaPipe model ==="
mkdir -p models
if [ ! -f models/face_landmarker.task ]; then
    curl -fsSL -o models/face_landmarker.task \
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
    echo "Model downloaded."
fi

echo "=== Converting icon ==="
uv run python tools/convert_icon.py
echo "=== Building with PyInstaller ==="
uv run pyinstaller --clean --noconfirm MisterTimer.spec

echo "=== Build complete ==="
echo "Output: dist/MisterTimer/"
if [ -f "dist/MisterTimer/MisterTimer.exe" ]; then
    echo "Windows: dist/MisterTimer/MisterTimer.exe"
else
    echo "Binary: dist/MisterTimer/MisterTimer"
fi
