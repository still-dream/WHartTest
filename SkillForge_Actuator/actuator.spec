# -*- mode: python ; coding: utf-8 -*-
"""
SkillForgeTest Actuator PyInstaller 打包配置（精准裁剪版）

裁剪策略：
  - PySide6 只打包 QtCore / QtGui / QtWidgets（GUI 实际只用这三个）
  - 其余 18+ 个 PySide6 子模块（QtWebEngine、QtQuick、Qt3D、QtPdf、QtMultimedia...）
    全部 exclude，预计节省 ~580 MB
  - 显式过滤 DLL，把 Qt6WebEngineCore.dll (195 MB)、opengl32sw.dll (20 MB)、
    FFmpeg 编解码器 (15 MB) 等一并剔除
  - 同时裁掉 matplotlib / numpy / pandas / scipy / PIL / cv2 / tkinter 等无关重模块

使用方法:
    pyinstaller actuator.spec

生成文件:
    dist/SkillForgeTest_Actuator/  - 包含所有依赖的目录
    dist/SkillForgeTest_Actuator/SkillForgeTest_Actuator.exe  - 主程序
"""

import sys
import glob
import re
from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
)


# ----------------------------------------------------------------------------
# 1. Playwright / pydantic / httpx 等与 GUI 无关的依赖，全量收集
# ----------------------------------------------------------------------------
playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all('playwright')
pydantic_datas, pydantic_binaries, pydantic_hiddenimports = collect_all('pydantic')
pydantic_core_datas, pydantic_core_binaries, pydantic_core_hiddenimports = collect_all('pydantic_core')
httpx_datas, httpx_binaries, httpx_hiddenimports = collect_all('httpx')
httpcore_datas, httpcore_binaries, httpcore_hiddenimports = collect_all('httpcore')

# ----------------------------------------------------------------------------
# 2. PySide6：只收集 GUI 真正用到的 QtCore / QtGui / QtWidgets
#    用白名单 collect_submodules 替代黑名单 collect_all，从源头杜绝 18+ 个
#    重型子模块被拉入
# ----------------------------------------------------------------------------
PYSIDE6_KEEP_MODULES = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
]

pyside6_hiddenimports = []
for mod in PYSIDE6_KEEP_MODULES:
    pyside6_hiddenimports.extend(collect_submodules(mod))

# shiboken6 是 PySide6 的 C++ 绑定，必须保留（全量才 ~3 MB，可忽略）
shiboken6_datas, shiboken6_binaries, shiboken6_hiddenimports = collect_all('shiboken6')

# PySide6 资源文件（Qt 的翻译、QSS 主题等），只取必要的部分
pyside6_datas = []
for src in collect_data_files('PySide6', includes=['*.qm', 'Qt/plugins/platforms/*.dll']):
    pyside6_datas.append(src)

# 由于 collect_submodules 不返回 binaries，需要从 site-packages 手动挑选 DLL
import site
import os
_pyside6_root = None
for sp in site.getsitepackages():
    candidate = os.path.join(sp, 'PySide6')
    if os.path.isdir(candidate):
        _pyside6_root = candidate
        break

pyside6_binaries = []
if _pyside6_root:
    # 平台插件（QWindows.dll 等）必须包含，否则 QApplication 启动不了
    platforms_dir = os.path.join(_pyside6_root, 'plugins', 'platforms')
    if os.path.isdir(platforms_dir):
        for f in os.listdir(platforms_dir):
            if f.endswith('.dll'):
                pyside6_binaries.append(
                    (os.path.join(platforms_dir, f), 'PySide6/plugins/platforms')
                )
    # 其它必需插件（图像、字体、样式等）
    for plugin_subdir in ('imageformats', 'styles', 'iconengines'):
        d = os.path.join(_pyside6_root, 'plugins', plugin_subdir)
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith('.dll'):
                    pyside6_binaries.append(
                        (os.path.join(d, f), f'PySide6/plugins/{plugin_subdir}')
                    )

# ----------------------------------------------------------------------------
# 3. 二进制白名单过滤：剔除 PySide6 目录里的"重型但用不到"的 DLL
#    （Qt6WebEngineCore.dll、opengl32sw.dll、Qt6Pdf*、Qt6Quick3D*、FFmpeg 等）
# ----------------------------------------------------------------------------
EXCLUDE_BINARY_PATTERNS = [
    r'Qt6WebEngine.*\.dll$',
    r'Qt6Pdf.*\.dll$',
    r'Qt6Quick3D.*\.dll$',
    r'Qt63D.*\.dll$',
    r'Qt6Multimedia.*\.dll$',
    r'Qt6Svg.*\.dll$',
    r'Qt6Sql.*\.dll$',
    r'Qt6NetworkAuth.*\.dll$',
    r'Qt6OpenGL.*\.dll$',
    r'Qt6Charts.*\.dll$',
    r'Qt6DataVisualization.*\.dll$',
    r'Qt6Graphs.*\.dll$',
    r'Qt6Bluetooth.*\.dll$',
    r'Qt6Sensors.*\.dll$',
    r'Qt6SerialPort.*\.dll$',
    r'Qt6Positioning.*\.dll$',
    r'Qt6Nfc.*\.dll$',
    r'Qt6WebSockets.*\.dll$',
    r'Qt6WebChannel.*\.dll$',
    r'Qt6Scxml.*\.dll$',
    r'Qt6Test.*\.dll$',
    r'Qt6RemoteObjects.*\.dll$',
    r'Qt6TextToSpeech.*\.dll$',
    r'Qt6VirtualKeyboard.*\.dll$',
    r'Qt6Xml.*\.dll$',
    r'Qt6Designer.*\.dll$',
    r'Qt6Help.*\.dll$',
    r'Qt6PdfQuick.*\.dll$',
    r'Qt6QmlCompiler.*\.dll$',
    r'Qt6QmlMeta.*\.dll$',
    r'Qt6QmlModels.*\.dll$',
    r'Qt6QmlWorkerScript.*\.dll$',
    r'Qt6QuickControls2.*\.dll$',
    r'Qt6QuickDialogs2.*\.dll$',
    r'Qt6QuickLayouts.*\.dll$',
    r'Qt6QuickParticles.*\.dll$',
    r'Qt6QuickShapes.*\.dll$',
    r'Qt6QuickTemplates2.*\.dll$',
    r'Qt6QuickTest.*\.dll$',
    r'Qt6QuickWidgets.*\.dll$',
    r'Qt63DAnimation.*\.dll$',
    r'Qt63DCore.*\.dll$',
    r'Qt63DExtras.*\.dll$',
    r'Qt63DInput.*\.dll$',
    r'Qt63DLogic.*\.dll$',
    r'Qt63DQuick.*\.dll$',
    r'Qt63DQuickAnimation.*\.dll$',
    r'Qt63DQuickExtras.*\.dll$',
    r'Qt63DQuickInput.*\.dll$',
    r'Qt63DQuickRender.*\.dll$',
    r'Qt63DQuickScene2D.*\.dll$',
    r'Qt63DRender.*\.dll$',
    r'opengl32sw\.dll$',
    r'avcodec-.*\.dll$',
    r'avformat-.*\.dll$',
    r'avutil-.*\.dll$',
    r'swscale-.*\.dll$',
    r'swresample-.*\.dll$',
    r'd3dcompiler_47\.dll$',
    r'libGLES.*\.dll$',
]
EXCLUDE_BINARY_REGEX = re.compile('|'.join(EXCLUDE_BINARY_PATTERNS), re.IGNORECASE)


def _filter_binaries(binaries):
    """剔除匹配 EXCLUDE_BINARY_PATTERNS 的 DLL"""
    kept, dropped = [], []
    for entry in binaries:
        # entry 形如 (src_path, 'dest_dir') 或 (src_path, 'dest_dir', 'TYPE')
        src = entry[0]
        if EXCLUDE_BINARY_REGEX.search(src):
            dropped.append(os.path.basename(src))
        else:
            kept.append(entry)
    if dropped:
        print(f"[裁剪] 剔除 {len(dropped)} 个重型 DLL:")
        for name in sorted(set(dropped)):
            print(f"  - {name}")
    return kept


# 对所有与 Qt/PySide6 相关的二进制统一过滤
all_binaries_before = list(
    playwright_binaries
    + pydantic_binaries
    + pydantic_core_binaries
    + pyside6_binaries
    + shiboken6_binaries
    + httpx_binaries
    + httpcore_binaries
)
all_binaries = _filter_binaries(all_binaries_before)

# ----------------------------------------------------------------------------
# 4. 收集 site-packages 根目录的 mypyc 编译模块（pydantic / httpcore 等）
# ----------------------------------------------------------------------------
mypyc_binaries = []
for sp in site.getsitepackages():
    for pyd in glob.glob(f"{sp}/*mypyc*.pyd"):
        mypyc_binaries.append((pyd, '.'))
    for pyd in glob.glob(f"{sp}/*mypyc*.so"):
        mypyc_binaries.append((pyd, '.'))
all_binaries.extend(mypyc_binaries)

# ----------------------------------------------------------------------------
# 5. PyInstaller Analysis
# ----------------------------------------------------------------------------
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=all_binaries,
    datas=[
        ('config.example.toml', '.'),
        ('data/SkillForgeTest.png', 'data'),
        *playwright_datas,
        *pydantic_datas,
        *pydantic_core_datas,
        *pyside6_datas,
        *shiboken6_datas,
        *httpx_datas,
        *httpcore_datas,
    ],
    hiddenimports=[
        # Playwright
        'playwright',
        'playwright.async_api',
        'playwright.sync_api',
        'playwright._impl',
        'playwright._impl._driver',
        *playwright_hiddenimports,

        # Pydantic
        'pydantic',
        'pydantic_core',
        *pydantic_hiddenimports,
        *pydantic_core_hiddenimports,

        # PySide6（只保留 QtCore/QtGui/QtWidgets 三个子包）
        *pyside6_hiddenimports,
        *shiboken6_hiddenimports,

        # HTTP / WebSocket
        *httpx_hiddenimports,
        *httpcore_hiddenimports,
        'websockets',
        'websockets.legacy',
        'websockets.legacy.client',
        'anyio',
        'anyio._backends._asyncio',
        'h11',
        'sniffio',

        # TOML
        'tomli',
        'tomllib',
        'tomli_w',

        # 本地模块
        'browser_installer',
        'websocket_client',
        'consumer',
        'executor',
        'models',
        'data_processor',
        'gui',
        'gui.login_window',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ------------------------------------------------------------------
        # PySide6：白名单策略下这里再补一刀，确保 18+ 个子模块不混入
        # ------------------------------------------------------------------
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtPdf',
        'PySide6.QtPdfQuick',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtQuick3D',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.Qt3DExtras',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
        'PySide6.QtSql',
        'PySide6.QtNetwork',
        'PySide6.QtNetworkAuth',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtGraphs',
        'PySide6.QtBluetooth',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtPositioning',
        'PySide6.QtNfc',
        'PySide6.QtWebSockets',
        'PySide6.QtWebChannel',
        'PySide6.QtScxml',
        'PySide6.QtTest',
        'PySide6.QtRemoteObjects',
        'PySide6.QtTextToSpeech',
        'PySide6.QtVirtualKeyboard',
        'PySide6.QtXml',
        'PySide6.QtXmlPatterns',
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtPrintSupport',
        'PySide6.QtDBus',
        'PySide6.QtConcurrent',
        'PySide6.QtQml',

        # ------------------------------------------------------------------
        # 其它与执行器无关的重型 Python 库
        # ------------------------------------------------------------------
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'pytest_asyncio',
        'sphinx',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SkillForgeTest_Actuator',
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
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        'Qt6WebEngineCore.dll',
        'Qt6Pdf.dll',
        'opengl32sw.dll',
        'avcodec-*.dll',
        'avformat-*.dll',
    ],
    name='SkillForgeTest_Actuator',
)
