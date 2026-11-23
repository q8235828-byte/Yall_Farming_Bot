# -*- mode: python ; coding: utf-8 -*-
import os

BLOCK_CIPHER = None

a = Analysis(
    ['app_launcher.py'],
    pathex=['.', 'dashboard', 'today_downloads', 'today_downloads/qaiser new test'],
    binaries=[],
    datas=[
        ('dashboard/templates', 'dashboard/templates'),
        ('dashboard/templates', 'templates'),
        ('dashboard', 'dashboard'),
        ('today_downloads', 'today_downloads')
    ],
    hiddenimports=[
        'dashboard',
        'dashboard.server',
        'dashboard.licensing',
        'google_sheet_sync',
        'master_pipeline',
        'screen_detector',
        'fast_screen_engine',
        'free_reward_ad_watcher',
        'lobby_navigator',
        'main_login_page',
        'login_form_handler',
        'flask',
        'jinja2',
        'cv2',
        'numpy',
        'uiautomator2'
    ],
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
    name='YallaFarmingStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
    name='YallaFarmingStudio',
)
