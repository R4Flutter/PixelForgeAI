# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for PixelForgeAI.

Build (from the project root):

    pip install -r requirements.txt -r requirements-gui.txt pyinstaller
    pyinstaller packaging/pixelforgeai.spec --noconfirm

Notes
-----
* Onedir (not onefile): the app bundles Real-ESRGAN weights + rembg/onnxruntime
  models, which makes a onefile archive painfully slow to extract on every
  launch. A folder install extracts once and starts fast.
* The existing AI scripts (scripts/) and the black-box contract in backend/job
  are imported normally — PyInstaller's analysis picks them up. rembg and
  onnxruntime ship data files (model manifests) that must be collected
  explicitly; their submodules are added as hidden imports.
* themes/, config/, assets/, models/ are bundled as data so the QSS theme,
  default settings, branding, and model weights resolve at runtime.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [
    ("themes", "themes"),
    ("config", "config"),
    ("assets", "assets"),
    ("models", "models"),
    # Ed25519 public key for licence verification. The PRIVATE key
    # (tools/keys/license_priv.pem) is NEVER bundled - it stays on the
    # developer's machine and is used only by tools/keygen.py.
    ("backend/keys", "backend/keys"),
]

# rembg / onnxruntime ship model manifests and provider DLLs as data.
datas += collect_data_files("rembg")
datas += collect_data_files("onnxruntime")

hiddenimports = [
    "PySide6.QtSvg",
    "PySide6.QtNetwork",
    # Licence verification layer.
    "cryptography",
    "cryptography.hazmat.primitives.asymmetric.ed25519",
]
hiddenimports += collect_submodules("rembg")
hiddenimports += collect_submodules("onnxruntime")

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PyQt6"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PixelForgeAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    # PyInstaller wants an .ico on Windows. Provide assets/logo.ico when ready;
    # leaving None keeps the default Python icon rather than erroring on an SVG.
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="PixelForgeAI",
)
