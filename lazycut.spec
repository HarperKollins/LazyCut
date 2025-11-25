# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import sys
import os

block_cipher = None

# --- COLLECT DEPENDENCIES ---
datas = []
binaries = []
hiddenimports = [
    'customtkinter', 
    'moviepy', 
    'whisper', 
    'google.generativeai', 
    'PIL', 
    'colorlog', 
    'updater', 
    'packaging', 
    'requests', 
    'soundfile', 
    'torch'
]

# Collect customtkinter data
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Collect whisper data (if needed, usually handled by hook-whisper but good to be safe)
tmp_ret = collect_all('whisper')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Add Assets
datas += [('assets', 'assets'), ('brolls', 'brolls')]

# --- ANALYSIS ---
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- EXE ---
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LazyCut',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, # Hide console for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None, # Add icon if available, e.g. 'assets/icon.ico'
)

# --- COLLECT ---
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LazyCut',
)
