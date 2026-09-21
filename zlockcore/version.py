from pathlib import Path
from re import fullmatch
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, QRunnable, Signal


VERSION_FILE = Path(__file__).with_name('version.txt')
VERSION_URL = 'https://zoardgodor.github.io/ZLockCore/version.txt'
UPDATE_URL = 'https://zoardgodor.github.io/ZLockCore/'


def _read_version_file() -> str:
    try:
        return VERSION_FILE.read_text(encoding='utf-8').strip()
    except Exception:
        return ''


APP_VERSION = _read_version_file() or 'unknown'


def app_version() -> str:
    value = _read_version_file()
    if value:
        return value
    return APP_VERSION


def _normalise_version(value: str) -> str:
    return value.strip().lower().removeprefix('v')


def _is_version(value: str) -> bool:
    return bool(fullmatch(r'v?\d+(?:\.\d+){1,3}', value.strip(), flags=2))


class VersionCheckSignals(QObject):
    finished = Signal(str)


class VersionCheckTask(QRunnable):
    def __init__(self, current_version: str):
        super().__init__()
        self.setAutoDelete(False)
        self.current_version = current_version
        self.signals = VersionCheckSignals()

    def run(self) -> None:
        try:
            request = Request(VERSION_URL, headers={'User-Agent': 'ZLockCore'})
            with urlopen(request, timeout=3) as response:
                remote_version = response.read(128).decode('utf-8').strip()
            if (
                _is_version(remote_version)
                and _normalise_version(remote_version) != _normalise_version(self.current_version)
            ):
                self.signals.finished.emit(remote_version)
                return
        except Exception:
            pass
        self.signals.finished.emit('')
