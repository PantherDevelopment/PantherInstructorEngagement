# build-mac.spec
# PyInstaller spec for macOS build

import os
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets/icon.png',   'assets'),
        ('assets/icon.icns',  'assets'),
        ('config.yaml',       '.'),
        ('src',               'src'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'keyring',
        'keyring.backends',
        'keyring.backends.macOS',
        'keyring.backends.fail',
        'zoneinfo',
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.utils',
        'yaml',
        'requests',
        'PIL',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pandas', 'numpy', 'matplotlib'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PantherInstructorEngagement',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PantherInstructorEngagement',
)

app = BUNDLE(
    coll,
    name='PantherInstructorEngagement.app',
    icon='assets/icon.icns',
    bundle_identifier='edu.fit.pantherinstructorengagement',
    version=Path('VERSION').read_text().strip(),
    info_plist={
        'NSPrincipalClass':                 'NSApplication',
        'NSAppleScriptEnabled':             False,
        'CFBundleDisplayName':              'Panther Instructor Engagement',
        'CFBundleShortVersionString':       Path('VERSION').read_text().strip(),
        'NSHighResolutionCapable':          True,
        'LSMinimumSystemVersion':           '10.15',
    },
)
