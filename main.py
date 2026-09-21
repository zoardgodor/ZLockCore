import sys
import traceback

from PySide6.QtWidgets import QApplication

from zlockcore.config import app_data_dir
from zlockcore.ui import MainWindow
from zlockcore.version import app_version


def report_unhandled_exception(exc_type, exc_value, exc_traceback):
    details = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        crash_log = app_data_dir() / 'crash.log'
        with crash_log.open('a', encoding='utf-8') as stream:
            stream.write(details)
            stream.write('\n' + ('-' * 80) + '\n')
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def main() -> int:
    sys.excepthook = report_unhandled_exception
    application = QApplication(sys.argv)
    application.setApplicationName('ZLockCore')
    application.setApplicationVersion(app_version())
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == '__main__':
    raise SystemExit(main())
