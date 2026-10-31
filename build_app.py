"""Build a standalone app on macOS or Windows, without collecting project data."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent
    parser.add_argument('--output', type=Path, default=root.parent)
    args = parser.parse_args()
    if sys.platform not in {'darwin', 'win32'}:
        raise SystemExit('请在 macOS 构建 .app，在 Windows 构建 Windows 应用。')
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='project-notes-build-') as temp:
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
            '--distpath', str(Path(temp) / 'dist'), '--workpath', str(Path(temp) / 'work'),
            str(root / 'project_notes.spec')], check=True, cwd=root)
        name = '项目札记.app' if sys.platform == 'darwin' else '项目札记'
        built = Path(temp) / 'dist' / name
        destination = args.output.resolve() / name
        # This directory contains the application only, never project records.
        if destination.exists():
            if any((destination / name).exists() for name in ('项目资料', 'projects', '正在使用文件')):
                raise SystemExit('输出目录含项目资料，未覆盖。请选择独立的程序输出目录。')
            marker = destination / 'Contents' / 'Info.plist' if sys.platform == 'darwin' else destination / '项目札记.exe'
            if not marker.is_file():
                raise SystemExit('输出位置已有其他文件夹，未覆盖。')
            shutil.rmtree(destination)
        shutil.copytree(built, destination, symlinks=True)
    print('已构建：' + str(destination))


if __name__ == '__main__':
    main()
