import os
import platform
from pathlib import Path


APP_NAME = 'ZLockCore'
CONTAINER_SUFFIX = '.zlock'
LEGACY_META = 'vault.meta.json'
LEGACY_STORAGE = 'storage'
LEGACY_PLAIN = 'plain'


def app_data_dir() -> Path:
    if platform.system() == 'Windows':
        base = Path(os.getenv('APPDATA') or Path.home())
    elif platform.system() == 'Darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.getenv('XDG_CONFIG_HOME') or (Path.home() / '.config'))
    result = base / 'ZLockCore'
    result.mkdir(parents=True, exist_ok=True)
    return result


def workspace_dir() -> Path:
    base = Path(os.getenv('TEMP') or os.getenv('TMP') or '/tmp') / 'ZLockCore' / 'workspaces'
    base.mkdir(parents=True, exist_ok=True)
    return base


def registry_path() -> Path:
    return app_data_dir() / 'vaults.json'


def legacy_registry_path() -> Path:
    return app_data_dir() / 'zlockcore_manager.json'
