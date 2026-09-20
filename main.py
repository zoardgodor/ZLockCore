import sys

from PySide6.QtWidgets import QApplication

from zlockcore.ui import MainWindow


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName('ZLockCore')
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == '__main__':
    raise SystemExit(main())
