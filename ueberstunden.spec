# -*- mode: python ; coding: utf-8 -*-
# Plattformübergreifende PyInstaller-Konfiguration.
# Build-Befehl (auf der jeweiligen Zielplattform ausführen):
#   pyinstaller ueberstunden.spec
# Oder komfortabler über das Build-Skript:
#   python build.py

import sys
import os

APP_NAME = 'Überstundenrechner'
if sys.platform == 'darwin':
    ICON_FILE = 'icon.icns'
elif sys.platform == 'win32':
    ICON_FILE = 'icon.ico'
else:
    ICON_FILE = 'icon.png'

datas = []
if os.path.exists(ICON_FILE):
    datas.append((ICON_FILE, '.'))

a = Analysis(
    ['ueberstunden.py'],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    excludes=[
        # Ungenutzte PyQt6-Module
        'PyQt6.QtBluetooth', 'PyQt6.QtDBus', 'PyQt6.QtDesigner',
        'PyQt6.QtHelp', 'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtNetwork', 'PyQt6.QtNfc', 'PyQt6.QtOpenGL',
        'PyQt6.QtOpenGLWidgets', 'PyQt6.QtPositioning',
        'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtQuick3D',
        'PyQt6.QtRemoteObjects', 'PyQt6.QtSensors', 'PyQt6.QtSerialPort',
        'PyQt6.QtSql', 'PyQt6.QtTest', 'PyQt6.QtWebChannel',
        'PyQt6.QtWebSockets', 'PyQt6.QtXml',
        # Ungenutzte matplotlib-Backends
        'matplotlib.backends.backend_pdf',
        'matplotlib.backends.backend_ps',
        'matplotlib.backends.backend_svg',
        'matplotlib.backends.backend_webagg',
        'matplotlib.backends.backend_wx',
        'matplotlib.backends.backend_gtk3',
        'matplotlib.backends.backend_gtk4',
        'matplotlib.backends.backend_tk',
        # Sonstiges
        'tkinter', 'xmlrpc', 'multiprocessing',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name=APP_NAME,
        console=False,
        icon=ICON_FILE if os.path.exists(ICON_FILE) else None,
    )
    coll = COLLECT(
        exe, a.binaries, a.datas,
        name=APP_NAME,
    )
    app = BUNDLE(
        coll,
        name=f'{APP_NAME}.app',
        icon=ICON_FILE if os.path.exists(ICON_FILE) else None,
        bundle_identifier='de.combase.ueberstundenrechner',
        info_plist={
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.14',
            'CFBundleShortVersionString': '1.0.0',
        },
    )

else:
    # Windows und Linux: onedir für schnellen Start (kein Entpacken bei jedem Launch)
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name=APP_NAME,
        console=False,
        icon=ICON_FILE if os.path.exists(ICON_FILE) else None,
    )
    coll = COLLECT(
        exe, a.binaries, a.datas,
        name=APP_NAME,
    )
