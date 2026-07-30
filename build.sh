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

echo "=== Building with PyInstaller ==="
echo "=== Converting icon ==="
uv run python -c "from PIL import Image; img = Image.open('icon.png'); img.save('icon.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"
uv run pyinstaller --clean --noconfirm MisterTimer.spec

echo "=== Build complete ==="
echo "Output: dist/MisterTimer/"
if [ -f "dist/MisterTimer/MisterTimer.exe" ]; then
    echo "Windows: dist/MisterTimer/MisterTimer.exe"
else
    echo "Binary: dist/MisterTimer/MisterTimer"
fi
