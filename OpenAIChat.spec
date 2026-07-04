# PyInstaller spec for building a double-clickable macOS .app bundle.

import plistlib

from PyInstaller.utils.hooks import collect_submodules


block_cipher = None
with open("Info.plist", "rb") as plist_file:
    info_plist = plistlib.load(plist_file)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules("keyring.backends"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OpenAI Chat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="OpenAI Chat",
)

app = BUNDLE(
    coll,
    name="OpenAI Chat.app",
    icon=None,
    bundle_identifier="com.example.openaichat",
    info_plist=info_plist,
)
