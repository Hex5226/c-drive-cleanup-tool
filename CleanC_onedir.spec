# -*- mode: python ; coding: utf-8 -*-
# onedir 打包配置（Velopack 在线更新要求 onedir，不能用 onefile）
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# customtkinter 需要收集主题/字体等数据文件，否则打包后 GUI 报错
ctk_datas = collect_data_files('customtkinter')
ctk_hidden = collect_submodules('customtkinter')

a = Analysis(
    ['CleanC_GUI.py'],
    pathex=[],
    binaries=[],
    datas=[('F:\\CleanC_Project\\assets\\CleanC.ico', '.')] + ctk_datas,
    hiddenimports=['CleanC', 'updater'] + ctk_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'cv2'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CleanC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon='F:\\CleanC_Project\\assets\\CleanC.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CleanC',
)
