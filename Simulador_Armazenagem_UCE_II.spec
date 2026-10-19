# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/Mário Cezar Souza/Documents/003 - UNIDADE CURRICULAR DE EXTENSÃO II UCE II/Nova pasta/Simulador_Desktop_v4.6/simulador_desktop.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/Mário Cezar Souza/Documents/003 - UNIDADE CURRICULAR DE EXTENSÃO II UCE II/Nova pasta/Simulador_Desktop_v4.6/simulador.ico', '.'), ('C:/Users/Mário Cezar Souza/Documents/003 - UNIDADE CURRICULAR DE EXTENSÃO II UCE II/Nova pasta/Simulador_Desktop_v4.6/logo_72.png', '.'), ('C:/Users/Mário Cezar Souza/Documents/003 - UNIDADE CURRICULAR DE EXTENSÃO II UCE II/Nova pasta/Simulador_Desktop_v4.6/logo_simulador.jpg', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PySide6'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Simulador_Armazenagem_UCE_II',
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
    icon=['C:/Users/Mário Cezar Souza/Documents/003 - UNIDADE CURRICULAR DE EXTENSÃO II UCE II/Nova pasta/Simulador_Desktop_v4.6/simulador.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Simulador_Armazenagem_UCE_II',
)
