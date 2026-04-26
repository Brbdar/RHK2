# -*- mode: python ; coding: utf-8 -*-
# Refactor v1.33: standalone/RHK_Befundassistent.spec - Cross-platform PyInstaller spec (relative paths, data files included)

from __future__ import annotations

from pathlib import Path
import sys

# Project root is the parent directory of this spec file (./standalone/..)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rhk_release_manifest import build_pyinstaller_datas, get_release_build_config

BUILD = get_release_build_config(ROOT)
ENTRY = str((ROOT / BUILD["entry_point"]).resolve())

# -----------------------------------------------------------------------------
# Data files (non-Python) required at runtime
# -----------------------------------------------------------------------------
datas = build_pyinstaller_datas(ROOT)

# -----------------------------------------------------------------------------
# Hidden imports (dynamic/lazy imports used throughout the app)
# -----------------------------------------------------------------------------
hiddenimports = [
    # PDF backends (lazy imports)
    "fitz",
    "pypdf",
    "PyPDF2",
    # Image/OCR backends (optional)
    "PIL",
    "PIL.Image",
    "PIL.ImageOps",
    "PIL.ImageEnhance",
    "numpy",
    "rapidocr_onnxruntime",
    "onnxruntime",
    "pytesseract",
    # Reports
    "reportlab",
]

a = Analysis(
    [ENTRY],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="RHK_Befundassistent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # clinical default: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RHK_Befundassistent",
)
