# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules, copy_metadata


datas = [("assets/icon.ico", "assets")]
binaries = []
hiddenimports = []

for package in ("customtkinter", "rembg", "keyring"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

binaries += collect_dynamic_libs("onnxruntime")
hiddenimports += collect_submodules("PIL")
hiddenimports += ["keyring.backends.Windows", "keyring.backends.fail"]
for distribution in ("rembg", "onnxruntime", "customtkinter", "keyring", "requests", "certifi"):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "IPython", "matplotlib", "numpy.testing"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PixelBatch",
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
    icon="assets/icon.ico",
)
