"""Small OS adapters; desktop and browser modes share the same storage."""
import contextlib
import os
from pathlib import Path
import subprocess
import sys


@contextlib.contextmanager
def file_lock(path):
    with Path(path).open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b'\0')
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


def open_path(path):
    path = str(Path(path).resolve())
    if sys.platform == 'win32':
        os.startfile(path)
    else:
        command = '/usr/bin/open' if sys.platform == 'darwin' else 'xdg-open'
        subprocess.run([command, path], check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, text=True, timeout=10)


def set_window_theme(theme):
    """Match macOS window chrome without changing the user's system appearance."""
    if sys.platform != 'darwin':
        return
    from AppKit import NSApplication, NSAppearance, NSAppearanceNameAqua, NSAppearanceNameDarkAqua
    from PyObjCTools.AppHelper import callAfter
    name = NSAppearanceNameDarkAqua if theme == 'dark' else NSAppearanceNameAqua
    callAfter(lambda: NSApplication.sharedApplication().setAppearance_(NSAppearance.appearanceNamed_(name)))
