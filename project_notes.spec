# Build on the target OS. User project data is deliberately excluded.
from pathlib import Path
import sys

root = Path(SPECPATH)
mac = sys.platform == 'darwin'
a = Analysis([str(root / 'desktop.py')], pathex=[str(root)],
    binaries=[], datas=[(str(root / 'dist'), 'dist'),
                        (str(root / '记录读写说明.md'), '.')],
    hiddenimports=['webview.platforms.cocoa' if mac else 'webview.platforms.edgechromium'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'tkinter', 'webview.platforms.qt',
              'webview.platforms.gtk', 'webview.platforms.cef'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='项目札记',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=str(root / 'assets' / ('app.icns' if mac else 'app.ico')))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='项目札记')
if mac:
    app = BUNDLE(coll, name='项目札记.app', icon=str(root / 'assets' / 'app.icns'),
        bundle_identifier='local.bujidao.project-notes', version='1.0.2',
        info_plist={'CFBundleDisplayName': '项目札记',
                    'CFBundleDevelopmentRegion': 'zh_CN',
                    'NSHighResolutionCapable': True,
                    'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True},
                    'LSMinimumSystemVersion': '12.0'})
