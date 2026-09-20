import io
import shutil
import secrets
from pathlib import Path

import qrcode
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QAction, QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QToolButton, QVBoxLayout, QWidget

from .config import CONTAINER_SUFFIX
from .i18n import Translator
from .keyring_store import KeyringError
from .mount import MountManager
from .registry import VaultRegistry
from .vault_service import VaultError, VaultService


def _password_eye_button(translator: Translator, field: QLineEdit) -> QToolButton:
    button = QToolButton()
    button.setCheckable(True)
    button.setAutoRaise(True)
    button.setFixedWidth(32)

    def update_icon(checked: bool):
        field.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        button.setText('\U0001f648' if checked else '\U0001f441')
        button.setToolTip(translator.t('password_hide' if checked else 'password_show'))

    button.toggled.connect(update_icon)
    update_icon(False)
    return button

class PasswordDialog(QDialog):
    def __init__(self, translator: Translator, title: str, confirm: bool = False, parent=None, input_label_key: str = 'enter_password'):
        super().__init__(parent)
        self.t = translator
        self.setWindowTitle(title)
        layout = QFormLayout(self)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.show_button = _password_eye_button(self.t, self.password)
        password_row = QHBoxLayout()
        password_row.addWidget(self.password)
        password_row.addWidget(self.show_button)
        layout.addRow(self.t.t(input_label_key), password_row)
        self.confirm = None
        if confirm:
            self.confirm = QLineEdit()
            self.confirm.setEchoMode(QLineEdit.Password)
            confirm_row = QHBoxLayout()
            confirm_row.addWidget(self.confirm)
            confirm_show = _password_eye_button(self.t, self.confirm)
            confirm_row.addWidget(confirm_show)
            layout.addRow(self.t.t('password_again'), confirm_row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def toggle_field(self, field: QLineEdit, button: QPushButton, checked: bool):
        field.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        button.setText(self.t.t('password_hide' if checked else 'password_show'))

    def toggle_password(self, checked: bool):
        self.password.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self.show_button.setText(self.t.t('password_hide' if checked else 'password_show'))


    def value(self) -> str | None:
        if self.exec() != QDialog.Accepted:
            return None
        password = self.password.text()
        if not password:
            QMessageBox.warning(self, self.t.t('error'), self.t.t('password_required'))
            return None
        if self.confirm is not None and password != self.confirm.text():
            QMessageBox.warning(self, self.t.t('error'), self.t.t('passwords_differ'))
            return None
        return password


class UnlockDialog(QDialog):
    def __init__(self, translator: Translator, mode: str, parent=None):
        super().__init__(parent)
        self.t = translator
        self.setWindowTitle(self.t.t('unlock'))
        layout = QFormLayout(self)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        row = QHBoxLayout()
        row.addWidget(self.password)
        show = _password_eye_button(self.t, self.password)
        row.addWidget(show)
        layout.addRow(self.t.t('password'), row)
        self.code = None
        if mode not in {'disabled', 'password_only'}:
            self.code = QLineEdit()
            self.code.setMaxLength(6)
            self.code.setPlaceholderText('000000')
            layout.addRow(self.t.t('enter_totp'), self.code)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _toggle(self, field: QLineEdit, button: QPushButton, checked: bool):
        field.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        button.setText(self.t.t('password_hide' if checked else 'password_show'))

    def credentials(self) -> tuple[str | None, str | None] | None:
        if self.exec() != QDialog.Accepted:
            return None
        return (self.password.text() if self.password else None, self.code.text() if self.code else None)


class TotpDialog(QDialog):
    def __init__(self, translator: Translator, service: VaultService, path: Path, master_key: bytes, parent=None):
        super().__init__(parent)
        self.t = translator
        self.service = service
        self.path = path
        self.master_key = master_key
        self.active = self.service.totp_config(path).get('mode', 'disabled') != 'disabled'
        self.pending_secret = ''
        self.pending_uri = ''
        self.setWindowTitle(self.t.t('totp_title'))
        root = QVBoxLayout(self)
        self.mode = QComboBox()
        for value, key in [('password_and_totp', 'password_and_totp'), ('totp_or_password', 'totp_or_password'), ('password_only', 'password_only')]:
            self.mode.addItem(self.t.t(key), value)
        self.issuer = QLineEdit('ZLockCore')
        self.account = QLineEdit(path.stem)
        form = QFormLayout()
        form.addRow(self.t.t('totp_mode'), self.mode)
        form.addRow(self.t.t('issuer'), self.issuer)
        form.addRow(self.t.t('account'), self.account)
        root.addLayout(form)
        self.info = QLabel()
        self.info.setWordWrap(True)
        root.addWidget(self.info)
        self.qr = QLabel()
        self.qr.setAlignment(Qt.AlignCenter)
        root.addWidget(self.qr)
        self.manual = QLineEdit()
        self.manual.setReadOnly(True)
        root.addWidget(QLabel(self.t.t('manual_secret')))
        root.addWidget(self.manual)
        self.code = QLineEdit()
        self.code.setMaxLength(6)
        self.code.setPlaceholderText('000000')
        root.addWidget(QLabel(self.t.t('verification_code')))
        root.addWidget(self.code)
        self.activate_button = QPushButton(self.t.t('activate_totp'))
        self.delete_button = QPushButton(self.t.t('delete_totp'))
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        root.addWidget(self.activate_button)
        root.addWidget(self.delete_button)
        root.addWidget(buttons)
        self.activate_button.clicked.connect(self.activate)
        self.delete_button.clicked.connect(self.delete)
        if self.active:
            self.show_active()
        else:
            self.show_pending()

    def render_qr(self):
        image = qrcode.make(self.pending_uri)
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        pixmap = QPixmap.fromImage(QImage.fromData(buffer.getvalue()))
        self.qr.setPixmap(pixmap.scaled(240, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def show_pending(self):
        self.active = False
        config, self.pending_secret, self.pending_uri = self.service.prepare_totp(self.path, self.mode.currentData(), self.issuer.text(), self.account.text())
        self.info.setText(self.t.t('scan_qr') + '\n' + self.t.t('totp_pending'))
        self.manual.setText(self.pending_secret)
        self.render_qr()
        self.code.show()
        self.activate_button.show()
        self.delete_button.hide()
        self.mode.setEnabled(True)
        self.issuer.setEnabled(True)
        self.account.setEnabled(True)

    def show_active(self):
        config = self.service.totp_config(self.path)
        index = self.mode.findData(config.get('mode'))
        if index >= 0:
            self.mode.setCurrentIndex(index)
        self.issuer.setText(config.get('issuer', 'ZLockCore'))
        self.account.setText(config.get('account', self.path.stem))
        self.info.setText(self.t.t('totp_active'))
        self.qr.hide()
        self.manual.hide()
        self.code.show()
        self.activate_button.hide()
        self.delete_button.show()
        self.mode.setEnabled(False)
        self.issuer.setEnabled(False)
        self.account.setEnabled(False)

    def activate(self):
        try:
            config, _, _ = self.service.prepare_totp(self.path, self.mode.currentData(), self.issuer.text(), self.account.text())
            config['mode'] = self.mode.currentData()
            self.service.activate_totp(self.path, self.master_key, config, self.pending_secret, self.code.text())
            QMessageBox.information(self, self.t.t('info'), self.t.t('totp_saved'))
            self.accept()
        except (VaultError, KeyringError) as exc:
            QMessageBox.critical(self, self.t.t('error'), str(exc))

    def delete(self):
        try:
            self.service.delete_totp(self.path, self.code.text())
            QMessageBox.information(self, self.t.t('info'), self.t.t('totp_deleted'))
            self.accept()
        except (VaultError, KeyringError) as exc:
            QMessageBox.critical(self, self.t.t('error'), str(exc))


class VaultSettingsDialog(QDialog):
    def __init__(self, translator: Translator, service: VaultService, path: Path, master_key: bytes, parent=None):
        super().__init__(parent)
        self.t = translator
        self.service = service
        self.path = path
        self.master_key = master_key
        self.setWindowTitle(self.t.t('settings'))
        layout = QVBoxLayout(self)
        totp = QGroupBox(self.t.t('totp_title'))
        totp_layout = QVBoxLayout(totp)
        totp_layout.addWidget(QLabel(self.t.t('scan_qr')))
        setup = QPushButton(self.t.t('activate_totp'))
        setup.clicked.connect(self.open_totp)
        totp_layout.addWidget(setup)
        layout.addWidget(totp)
        recovery = QGroupBox(self.t.t('recovery'))
        recovery_layout = QVBoxLayout(recovery)
        self.recovery_status = QLabel()
        recovery_layout.addWidget(self.recovery_status)
        generate = QPushButton()
        generate.clicked.connect(self.generate_recovery)
        disable = QPushButton(self.t.t('disable_recovery'))
        disable.clicked.connect(self.disable_recovery)
        self.generate_button = generate
        recovery_layout.addWidget(generate)
        recovery_layout.addWidget(disable)
        layout.addWidget(recovery)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self.update_recovery()

    def open_totp(self):
        TotpDialog(self.t, self.service, self.path, self.master_key, self).exec()

    def update_recovery(self):
        active = self.service.recovery_active(self.path)
        self.recovery_status.setText(f"{self.t.t('recovery_status')}: {self.t.t('recovery_active' if active else 'recovery_inactive')}")
        self.generate_button.setText(self.t.t('regenerate_recovery' if active else 'generate_recovery'))

    def generate_recovery(self):
        try:
            recovery = self.service.generate_recovery(self.path, self.master_key)
            self.update_recovery()
            show_secret(self.t, self.t.t('recovery'), self.t.t('recovery_generated'), recovery, self)
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), str(exc))

    def disable_recovery(self):
        try:
            self.service.disable_recovery(self.path, self.master_key)
            self.update_recovery()
            QMessageBox.information(self, self.t.t('info'), self.t.t('recovery_disabled'))
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), str(exc))


def show_secret(translator: Translator, title: str, message: str, value: str, parent=None):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(message))
    field = QLineEdit(value)
    field.setReadOnly(True)
    layout.addWidget(field)
    copy = QPushButton(translator.t('copy'))
    copy.clicked.connect(lambda: QApplication.clipboard().setText(value))
    layout.addWidget(copy)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.exec()


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
        self.setWindowTitle(self.t.t('title'))

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
        self.recover_button.setEnabled(unlocked or self.service.recovery_active(path))

    def clear_details(self):
        for label in [self.name_label, self.description_label, self.path_label, self.status_label]:
            label.clear()
        for button in [self.unlock_button, self.open_button, self.lock_button, self.recover_button, self.settings_button]:
            button.setEnabled(False)

    def create_vault(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, self.t.t('new_vault'), self.t.t('new_name'))
        if not ok or not name.strip() or name in self.registry.vaults:
            return
        description, ok = QInputDialog.getText(self, self.t.t('new_vault'), self.t.t('description_prompt'))
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
            recovery = ' '.join(secrets.choice(['river', 'tree', 'stone', 'cloud', 'light', 'key', 'garden', 'window']) for _ in range(24))
        path = Path(folder) / f'{name}{CONTAINER_SUFFIX}'
        try:
            self.service.create(path, password, description, recovery)
            self.registry.add(name, path)
            self.refresh()
            if recovery:
                show_secret(self.t, self.t.t('recovery'), self.t.t('recovery_info'), recovery, self)
            QMessageBox.information(self, self.t.t('info'), self.t.t('created', name=name))
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), self.t.t('operation_failed', error=str(exc)))

    def ask_password(self, confirm=False):
        return PasswordDialog(self.t, self.t.t('password'), confirm, self).value()

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
        if self.current in self.active:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.active[self.current][1].path)))

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
        VaultSettingsDialog(self.t, self.service, path, key, self).exec()
        self.update_details()

    def recover(self):
        path = self.selected_path()
        if not path:
            return
        unlocked = self.current in self.active
        if not unlocked and not self.service.recovery_active(path):
            QMessageBox.information(self, self.t.t('info'), self.t.t('no_recovery_locked'))
            return

        if unlocked:
            master_key = self.active[self.current][0]
        else:
            recovery = PasswordDialog(
                self.t,
                self.t.t('recover'),
                input_label_key='enter_recovery',
            ).value()
            if not recovery:
                return
            try:
                master_key = self.service.recover_master(path, recovery)
            except Exception:
                QMessageBox.critical(self, self.t.t('error'), self.t.t('recovery_invalid'))
                return

        new_password = self.ask_password(confirm=True)
        if not new_password:
            return
        try:
            self.service.change_password(path, master_key, new_password)
            QMessageBox.information(self, self.t.t('info'), self.t.t('password_changed'))
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), self.t.t('recover_failed', error=str(exc)))

    def import_vault(self):
        filename, _ = QFileDialog.getOpenFileName(self, self.t.t('import'), '', 'ZLock container (*.zlock)')
        if filename:
            path = Path(filename)
            name = path.stem
        else:
            folder = QFileDialog.getExistingDirectory(self, self.t.t('import'))
            if not folder:
                return
            path = Path(folder)
            name = path.name
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
        from PySide6.QtWidgets import QInputDialog
        if not self.current:
            return
        new_name, ok = QInputDialog.getText(self, self.t.t('rename'), self.t.t('new_name'))
        if not ok or not new_name or new_name in self.registry.vaults:
            return
        old_name = self.current
        path = self.selected_path()
        if old_name in self.active:
            self.lock()
        new_path = path.with_name(new_name + (CONTAINER_SUFFIX if path.is_file() else ''))
        try:
            path.rename(new_path)
            del self.registry.vaults[old_name]
            self.registry.vaults[new_name] = str(new_path)
            self.registry.save()
            self.current = new_name
            self.refresh()
            QMessageBox.information(self, self.t.t('info'), self.t.t('renamed', name=new_name))
        except Exception as exc:
            QMessageBox.critical(self, self.t.t('error'), self.t.t('operation_failed', error=str(exc)))

    def delete_vault(self):
        if not self.current or QMessageBox.question(self, self.t.t('confirm'), self.t.t('delete_confirm')) != QMessageBox.Yes:
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
