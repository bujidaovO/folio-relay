"""Resolve bundled resources and external, portable project data."""
import json
import os
from pathlib import Path
import sys


def resource_directory():
    return Path(__file__).resolve().parent


def application_directory():
    if not getattr(sys, 'frozen', False):
        return resource_directory().parent
    executable = Path(sys.executable).resolve()
    if sys.platform == 'darwin':
        return executable.parents[2].parent
    return executable.parent


def settings_path():
    if sys.platform == 'darwin':
        root = Path.home() / 'Library' / 'Application Support'
    elif sys.platform == 'win32':
        root = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:
        root = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    return root / '项目札记' / 'settings.json'


def default_data_directory():
    if os.environ.get('PROJECT_NOTES_DATA_DIR'):
        return Path(os.environ['PROJECT_NOTES_DATA_DIR']).expanduser().resolve()
    portable = application_directory() / '项目资料'
    if sys.platform == 'win32' and not portable.is_dir():
        sibling = application_directory().parent / '项目资料'
        if sibling.is_dir():
            portable = sibling
    try:
        settings = json.loads(settings_path().read_text(encoding='utf-8'))
        saved = Path(settings['dataDirectory'])
        if settings.get('applicationDirectory') == str(application_directory()) and saved.is_dir():
            return saved.resolve()
    except (OSError, ValueError, KeyError):
        pass
    if portable.is_dir() or not getattr(sys, 'frozen', False):
        return portable
    return Path.home() / 'Documents' / '项目札记' / '项目资料'
