import io
import shutil
from pathlib import Path

import qrcode
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QAction, QDesktopServices, QPixmap
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget, QCheckBox, QGroupBox

from .config import CONTAINER_SUFFIX
from .i18n import Translator
from .keyring_store import KeyringError
from .mount import MountManager
from .registry import VaultRegistry
from .vault_service import VaultError, VaultService


class TextDialog(QDialog):
    def __init__(self, title: str, label: str, password: bool = False, confirm: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QFormLayout(self)
        self.value = QLineEdit()
        self.value.setEchoMode(QLineEdit.Password if password else QLineEdit.Normal)
        layout.addRow(label, self.value)
        self.confirm = None
        if confirm:
            self.confirm = QLineEdit()
            self.confirm.setEchoMode(QLineEdit.Password)
            layout.addRow('Confirm', self.confirm)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def result(self) -> str | None:
        if self.exec() != QDialog.Accepted:
            return None
        value = self.value.text()
        if not value or (self.confirm is not None and value != self.confirm.text()):
            return None
        return value


class UnlockDialog(QDialog):
    def __init__(self, translator: Translator, mode: str, parent=None):
        super().__init__(parent)
        self.t = translator
        self.setWindowTitle(self.t.t('unlock'))
        layout = QFormLayout(self)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.code = QLineEdit()
        self.code.setMaxLength(6)
        self.code.setPlaceholderText('000000')
        if mode not in {'totp_only'}:
            layout.addRow(self.t.t('password'), self.password)
        if mode not in {'disabled', 'password_only'}:
            layout.addRow(self.t.t('enter_totp'), self.code)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def credentials(self) -> tuple[str | None, str | None] | None:
        if self.exec() != QDialog.Accepted:
            return None
        return self.password.text() or None, self.code.text() or None


class TotpDialog(QDialog):
    saved = Signal(str, str, str)

    def __init__(self, translator: Translator, service: VaultService, path: Path, master_key: bytes, parent=None):
        super().__init__(parent)
        self.t = translator
        self.service = service
        self.path = path
        self.master_key = master_key
        self.setWindowTitle(self.t.t('totp_title'))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.mode = QComboBox()
        modes = [('disabled', 'totp_disabled'), ('password_only', 'password_only'), ('totp_only', 'totp_only'), ('totp_or_password', 'totp_or_password'), ('password_and_totp', 'password_and_totp')]
        for value, key in modes:
            self.mode.addItem(self.t.t(key), value)
        self.issuer = QLineEdit('ZLockCore')
        self.account = QLineEdit(path.stem)
        form.addRow(self.t.t('totp_mode'), self.mode)
        form.addRow(self.t.t('issuer'), self.issuer)
        form.addRow(self.t.t('account'), self.account)
        layout.addLayout(form)
        self.qr = QLabel()
        self.qr.setAlignment(Qt.AlignCenter)
        self.manual = QLineEdit()
        self.manual.setReadOnly(True)
        self.info = QLabel(self.t.t('scan_qr'))
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        layout.addWidget(self.qr)
        layout.addWidget(QLabel(self.t.t('manual_secret')))
        layout.addWidget(self.manual)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.mode.currentIndexChanged.connect(self.update_preview)
        self.update_preview()

    def update_preview(self):
        if self.mode.currentData() == 'disabled':
            self.qr.clear()
            self.manual.clear()
            return
        preview = self.service.totp_config(self.path)
        if preview.get('mode') != self.mode.currentData():
            self.manual.setText('A mentéskor új kulcs készül')
            self.qr.clear()

    def save(self):
        try:
            config, secret, uri = self.service.configure_totp(self.path, self.master_key, self.mode.currentData(), self.issuer.text(), self.account.text())
            if secret:
                self.manual.setText(secret)
                image = qrcode.make(uri)
                buffer = io.BytesIO()
                image.save(buffer, format='PNG')
                self.qr.setPixmap(QPixmap.fromImage(__import__('PySide6.QtGui', fromlist=['QImage']).QImage.fromData(buffer.getvalue())).scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                QMessageBox.information(self, self.t.t('info'), self.t.t('totp_saved'))
                return
            QMessageBox.information(self, self.t.t('info'), self.t.t('totp_disabled_done'))
            self.accept()
        except KeyringError as exc:
            QMessageBox.critical(self, self.t.t('error'), self.t.t('keyring_error', error=str(exc)))
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), self.t.t('operation_failed', error=str(exc)))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.t = Translator()
        self.registry = VaultRegistry()
        self.service = VaultService()
        self.mount_manager = MountManager()
        self.active: dict[str, tuple[bytes, object]] = {}
        self.current: str | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.setMinimumSize(980, 620)
        self.setWindowTitle(self.t.t('title'))
        menu = self.menuBar().addMenu(self.t.t('language'))
        for code, label in [('hu', 'hungarian'), ('en', 'english')]:
            action = QAction(self.t.t(label), self)
            action.triggered.connect(lambda checked=False, value=code: self.set_language(value))
            menu.addAction(action)
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self.select)
        left.addWidget(QLabel(self.t.t('vaults')))
        left.addWidget(self.list)
        actions = QHBoxLayout()
        for key, handler in [('new_vault', self.create_vault), ('import', self.import_vault), ('rename', self.rename_vault), ('delete', self.delete_vault)]:
            button = QPushButton(self.t.t(key))
            button.clicked.connect(handler)
            actions.addWidget(button)
        left.addLayout(actions)
        root.addLayout(left, 1)
        panel = QGroupBox(self.t.t('details'))
        details = QVBoxLayout(panel)
        self.name_label = QLabel()
        self.description_label = QLabel()
        self.path_label = QLabel()
        self.status_label = QLabel()
        for label in [self.name_label, self.description_label, self.path_label, self.status_label]:
            label.setWordWrap(True)
            details.addWidget(label)
        details.addStretch()
        controls = QHBoxLayout()
        self.unlock_button = QPushButton(self.t.t('unlock'))
        self.open_button = QPushButton(self.t.t('open'))
        self.lock_button = QPushButton(self.t.t('lock'))
        self.recover_button = QPushButton(self.t.t('recover'))
        self.settings_button = QPushButton(self.t.t('settings'))
        self.unlock_button.clicked.connect(self.unlock)
        self.open_button.clicked.connect(self.open_vault)
        self.lock_button.clicked.connect(self.lock)
        self.recover_button.clicked.connect(self.recover)
        self.settings_button.clicked.connect(self.settings)
        for button in [self.unlock_button, self.open_button, self.lock_button, self.recover_button, self.settings_button]:
            controls.addWidget(button)
        details.addLayout(controls)
        root.addWidget(panel, 2)
        self.clear_details()

    def set_language(self, language: str):
        self.t.set_language(language)
        QMessageBox.information(self, self.t.t('info'), self.t.t('title') + '\nRestart the application to apply the language to every control.')

    def refresh(self):
        self.list.clear()
        for name in sorted(self.registry.vaults):
            self.list.addItem(name)

    def selected_path(self) -> Path | None:
        return Path(self.registry.vaults[self.current]) if self.current in self.registry.vaults else None

    def select(self, item: QListWidgetItem | None, previous=None):
        self.current = item.text() if item else None
        self.update_details()

    def update_details(self):
        path = self.selected_path()
        if not path:
            self.clear_details()
            return
        metadata = self.service.metadata(path)
        unlocked = self.current in self.active
        self.name_label.setText(f"{self.t.t('name')}: {self.current}")
        self.description_label.setText(f"{self.t.t('description')}: {metadata.get('description', '')}")
        self.path_label.setText(f"{self.t.t('path')}: {path}")
        self.status_label.setText(f"{self.t.t('status')}: {self.t.t('unlocked' if unlocked else 'locked')}")
        self.unlock_button.setEnabled(not unlocked)
        self.open_button.setEnabled(unlocked)
        self.lock_button.setEnabled(unlocked)
        self.settings_button.setEnabled(unlocked)
        self.recover_button.setEnabled(True)

    def clear_details(self):
        for label in [self.name_label, self.description_label, self.path_label, self.status_label]:
            label.clear()
        for button in [self.unlock_button, self.open_button, self.lock_button, self.recover_button, self.settings_button]:
            button.setEnabled(False)

    def create_vault(self):
        name, ok = __import__('PySide6.QtWidgets', fromlist=['QInputDialog']).QInputDialog.getText(self, self.t.t('new_vault'), self.t.t('new_name'))
        if not ok or not name.strip() or name in self.registry.vaults:
            return
        description, ok = __import__('PySide6.QtWidgets', fromlist=['QInputDialog']).QInputDialog.getText(self, self.t.t('new_vault'), self.t.t('description_prompt'))
        if not ok:
            return
        folder = QFileDialog.getExistingDirectory(self, self.t.t('choose_folder'))
        if not folder:
            return
        password = self.ask_password(confirm=True)
        if not password:
            return
        recovery = None
        if QMessageBox.question(self, self.t.t('recovery'), self.t.t('recovery_prompt')) == QMessageBox.Yes:
            recovery = ' '.join(__import__('secrets').choice(['river', 'tree', 'stone', 'cloud', 'light', 'key', 'garden', 'window']) for _ in range(24))
        path = Path(folder) / f'{name}{CONTAINER_SUFFIX}'
        try:
            self.service.create(path, password, description, recovery)
            self.registry.add(name, path)
            self.refresh()
            if recovery:
                self.show_secret(self.t.t('recovery'), self.t.t('recovery_info'), recovery)
            QMessageBox.information(self, self.t.t('info'), self.t.t('created', name=name))
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), self.t.t('operation_failed', error=str(exc)))

    def ask_password(self, confirm=False):
        dialog = TextDialog(self.t.t('password'), self.t.t('enter_password'), True, confirm, self)
        return dialog.result()

    def show_secret(self, title: str, message: str, value: str):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(message))
        field = QLineEdit(value)
        field.setReadOnly(True)
        layout.addWidget(field)
        copy = QPushButton(self.t.t('copy'))
        copy.clicked.connect(lambda: QApplication.clipboard().setText(value))
        layout.addWidget(copy)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def unlock(self):
        path = self.selected_path()
        if not path or not self.current:
            return
        mode = (self.service.metadata(path).get('totp') or {}).get('mode', 'disabled')
        credentials = UnlockDialog(self.t, mode, self).credentials()
        if credentials is None:
            return
        try:
            key = self.service.unlock(path, *credentials)
            workspace = self.service.extract(path, key)
            mount = self.mount_manager.mount(workspace, self.current)
            self.active[self.current] = (key, mount)
            self.update_details()
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), self.t.t('wrong_credentials') + f'\n{exc}')

    def open_vault(self):
        if self.current not in self.active:
            return
        mount = self.active[self.current][1]
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(mount.path)))

    def lock(self):
        if not self.current or self.current not in self.active:
            return
        path = self.selected_path()
        key, mount = self.active.pop(self.current)
        try:
            self.mount_manager.unmount(mount)
            self.service.pack(path, key)
            self.update_details()
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), self.t.t('operation_failed', error=str(exc)))

    def settings(self):
        if not self.current or self.current not in self.active:
            return
        path = self.selected_path()
        key = self.active[self.current][0]
        TotpDialog(self.t, self.service, path, key, self).exec()

    def recover(self):
        path = self.selected_path()
        if not path:
            return
        recovery = TextDialog(self.t.t('recover'), self.t.t('recovery'), True, False, self).result()
        if not recovery:
            return
        new_password = self.ask_password(confirm=True)
        if not new_password:
            return
        try:
            key = self.service.recover_master(path, recovery)
            self.service.change_password(path, key, new_password)
            QMessageBox.information(self, self.t.t('info'), self.t.t('password_changed'))
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), self.t.t('recover_failed', error=str(exc)))

    def import_vault(self):
        filename, _ = QFileDialog.getOpenFileName(self, self.t.t('import'), '', 'ZLock container (*.zlock)')
        if not filename:
            return
        path = Path(filename)
        name = path.stem
        if name in self.registry.vaults:
            return
        try:
            self.service.metadata(path)
            self.registry.add(name, path)
            self.refresh()
            QMessageBox.information(self, self.t.t('info'), self.t.t('imported', name=name))
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), self.t.t('operation_failed', error=str(exc)))

    def rename_vault(self):
        if not self.current:
            return
        new_name, ok = __import__('PySide6.QtWidgets', fromlist=['QInputDialog']).QInputDialog.getText(self, self.t.t('rename'), self.t.t('new_name'))
        if not ok or not new_name or new_name in self.registry.vaults:
            return
        path = self.selected_path()
        if self.current in self.active:
            self.lock()
        new_path = path.with_name(new_name + (CONTAINER_SUFFIX if path.is_file() else ''))
        try:
            path.rename(new_path)
            del self.registry.vaults[self.current]
            self.registry.vaults[new_name] = str(new_path)
            self.registry.save()
            self.current = new_name
            self.refresh()
            QMessageBox.information(self, self.t.t('info'), self.t.t('renamed', name=new_name))
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), self.t.t('operation_failed', error=str(exc)))

    def delete_vault(self):
        if not self.current:
            return
        if QMessageBox.question(self, self.t.t('confirm'), self.t.t('delete_confirm')) != QMessageBox.Yes:
            return
        name = self.current
        if name in self.active:
            self.lock()
        try:
            path = self.selected_path()
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            self.registry.remove(name)
            self.current = None
            self.refresh()
            self.clear_details()
            QMessageBox.information(self, self.t.t('info'), self.t.t('deleted', name=name))
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), self.t.t('operation_failed', error=str(exc)))

    def closeEvent(self, event):
        for name in list(self.active):
            self.current = name
            self.lock()
        event.accept()
