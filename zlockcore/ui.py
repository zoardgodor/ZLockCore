from . import ui_source
from .ui_source import *


class TotpDialog(ui_source.TotpDialog):
    def show_active(self):
        super().show_active()
        self.mode.setEnabled(True)

    def mode_changed(self):
        if not self.active:
            return
        try:
            self.service.set_totp_mode(self.path, self.mode.currentData())
        except VaultError as exc:
            QMessageBox.critical(self, self.t.t('error'), str(exc))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode.currentIndexChanged.connect(self.mode_changed)


class VaultSettingsDialog(ui_source.VaultSettingsDialog):
    def open_totp(self):
        TotpDialog(self.t, self.service, self.path, self.master_key, self).exec()


class MainWindow(ui_source.MainWindow):
    def settings(self):
        if not self.current or self.current not in self.active:
            return
        path = self.selected_path()
        key = self.active[self.current][0]
        VaultSettingsDialog(self.t, self.service, path, key, self).exec()
        self.update_details()
