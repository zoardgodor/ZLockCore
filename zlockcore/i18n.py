import json
from pathlib import Path

from .config import app_data_dir


TEXT = {
    'hu': {
        'title': 'ZLockCore — titkosított széfek', 'vaults': 'Széfek', 'new_vault': 'Új széf', 'import': 'Importálás', 'rename': 'Átnevezés', 'delete': 'Törlés', 'details': 'Széf részletei', 'name': 'Név', 'description': 'Leírás', 'path': 'Útvonal', 'status': 'Állapot', 'locked': 'Lezárva', 'unlocked': 'Feloldva', 'unlock': 'Feloldás', 'open': 'Széf megnyitása', 'lock': 'Lezárás', 'recover': 'Jelszó visszaállítása', 'settings': 'Beállítások', 'language': 'Nyelv', 'english': 'Angol', 'hungarian': 'Magyar', 'ok': 'OK', 'cancel': 'Mégse', 'error': 'Hiba', 'info': 'Információ', 'confirm': 'Megerősítés', 'yes': 'Igen', 'no': 'Nem', 'password': 'Jelszó', 'password_again': 'Jelszó újra', 'password_required': 'A jelszó nem lehet üres.', 'passwords_differ': 'A két jelszó nem egyezik.', 'enter_password': 'Add meg a jelszót:', 'enter_totp': 'Add meg a 6 számjegyű időalapú kódot:', 'select_vault': 'Válassz ki egy széfet.', 'wrong_credentials': 'A megadott hitelesítő adatok hibásak.', 'new_name': 'Széf neve', 'description_prompt': 'Leírás (opcionális)', 'choose_folder': 'Válaszd ki a konténer helyét', 'recovery': 'Helyreállítási kulcs', 'enter_recovery': 'Add meg a recovery kódot:', 'recovery_invalid': 'A recovery kód hibás.', 'recovery_prompt': 'Készüljön helyreállítási kulcs?', 'recovery_info': 'A helyreállítási kulcsot mentsd biztonságos helyre.', 'copy': 'Másolás', 'created': 'A széf létrejött: {name}', 'deleted': 'A széf törölve: {name}', 'imported': 'A széf importálva: {name}', 'renamed': 'A széf átnevezve: {name}', 'valid_container': 'Érvényes .zlock konténert válassz.', 'delete_confirm': 'Biztosan törlöd ezt a széfet? Ez nem vonható vissza.', 'totp_title': 'Időalapú kód és kétfaktoros hitelesítés', 'totp_mode': 'Használati mód', 'totp_disabled': 'Kikapcsolva', 'password_only': 'Csak jelszó', 'totp_or_password': 'Jelszó vagy időalapú kód', 'password_and_totp': 'Jelszó és időalapú kód együtt', 'issuer': 'Szolgáltató neve', 'account': 'Fiók neve', 'scan_qr': 'Olvasd be ezt a QR-kódot Apple Jelszavakba vagy Google Authenticatorba.', 'manual_secret': 'Kézzel beírható kulcs', 'verification_code': 'Ellenőrző kód', 'activate_totp': 'TOTP aktiválása', 'delete_totp': 'TOTP törlése', 'totp_pending': 'Az aktiváláshoz írd be a QR-kódhoz tartozó aktuális 6 számjegyű kódot.', 'totp_active': 'A TOTP aktív. A törléshez írd be az aktuális kódot.', 'totp_saved': 'A TOTP aktiválva.', 'totp_deleted': 'A TOTP törölve.', 'keyring_error': 'Az operációs rendszer kulcstartója nem érhető el: {error}', 'settings_locked': 'A beállítások csak feloldott széf mellett érhetők el.', 'recovery_missing': 'Ehhez a széfhez nincs aktív helyreállítási kulcs.', 'generate_recovery': 'Recovery kód létrehozása', 'regenerate_recovery': 'Recovery kód újragenerálása', 'disable_recovery': 'Recovery kikapcsolása', 'recovery_disabled': 'A recovery kikapcsolva.', 'recovery_generated': 'Az új recovery kód elkészült. Most csak egyszer látható.', 'new_password': 'Új jelszó', 'password_changed': 'A jelszó megváltozott.', 'recover_failed': 'A visszaállítás sikertelen: {error}', 'operation_failed': 'A művelet sikertelen: {error}', 'password_show': 'Jelszó megjelenítése', 'password_hide': 'Jelszó elrejtése', 'recovery_status': 'Recovery állapot', 'recovery_active': 'Aktív', 'recovery_inactive': 'Nincs beállítva', 'confirm_code': 'A művelethez aktuális 6 számjegyű kód szükséges.', 'no_recovery_locked': 'A jelszó visszaállítása nem használható, mert nincs aktív recovery kód.', 'confirm': 'Megerősítés', 'show': 'Megjelenítés', 'hide': 'Elrejtés',
    },
    'en': {
        'title': 'ZLockCore — encrypted vaults', 'vaults': 'Vaults', 'new_vault': 'New vault', 'import': 'Import', 'rename': 'Rename', 'delete': 'Delete', 'details': 'Vault details', 'name': 'Name', 'description': 'Description', 'path': 'Path', 'status': 'Status', 'locked': 'Locked', 'unlocked': 'Unlocked', 'unlock': 'Unlock', 'open': 'Open vault', 'lock': 'Lock', 'recover': 'Reset password', 'settings': 'Settings', 'language': 'Language', 'english': 'English', 'hungarian': 'Hungarian', 'ok': 'OK', 'cancel': 'Cancel', 'error': 'Error', 'info': 'Information', 'confirm': 'Confirmation', 'yes': 'Yes', 'no': 'No', 'password': 'Password', 'password_again': 'Password again', 'password_required': 'Password cannot be empty.', 'passwords_differ': 'The passwords do not match.', 'enter_password': 'Enter the password:', 'enter_totp': 'Enter the 6-digit time-based code:', 'select_vault': 'Select a vault.', 'wrong_credentials': 'The supplied credentials are invalid.', 'new_name': 'Vault name', 'description_prompt': 'Description (optional)', 'choose_folder': 'Choose the container location', 'recovery': 'Recovery key', 'enter_recovery': 'Enter the recovery code:', 'recovery_invalid': 'The recovery code is invalid.', 'recovery_prompt': 'Create a recovery key?', 'recovery_info': 'Store the recovery key in a safe place.', 'copy': 'Copy', 'created': 'Vault created: {name}', 'deleted': 'Vault deleted: {name}', 'imported': 'Vault imported: {name}', 'renamed': 'Vault renamed: {name}', 'valid_container': 'Choose a valid .zlock container.', 'delete_confirm': 'Delete this vault? This cannot be undone.', 'totp_title': 'Time-based code and two-factor authentication', 'totp_mode': 'Usage mode', 'totp_disabled': 'Disabled', 'password_only': 'Password only', 'totp_or_password': 'Password or time-based code', 'password_and_totp': 'Password and time-based code', 'issuer': 'Issuer name', 'account': 'Account name', 'scan_qr': 'Scan this QR code with Apple Passwords or Google Authenticator.', 'manual_secret': 'Manual entry secret', 'verification_code': 'Verification code', 'activate_totp': 'Activate TOTP', 'delete_totp': 'Delete TOTP', 'totp_pending': 'Enter the current 6-digit code belonging to this QR code to activate it.', 'totp_active': 'TOTP is active. Enter the current code to delete it.', 'totp_saved': 'TOTP activated.', 'totp_deleted': 'TOTP deleted.', 'keyring_error': 'The operating system keyring is unavailable: {error}', 'settings_locked': 'Settings are available only while the vault is unlocked.', 'recovery_missing': 'This vault has no active recovery key.', 'generate_recovery': 'Generate recovery code', 'regenerate_recovery': 'Regenerate recovery code', 'disable_recovery': 'Disable recovery', 'recovery_disabled': 'Recovery disabled.', 'recovery_generated': 'The new recovery code was generated. It is shown only once.', 'new_password': 'New password', 'password_changed': 'Password changed.', 'recover_failed': 'Recovery failed: {error}', 'operation_failed': 'Operation failed: {error}', 'password_show': 'Show password', 'password_hide': 'Hide password', 'recovery_status': 'Recovery status', 'recovery_active': 'Active', 'recovery_inactive': 'Not configured', 'confirm_code': 'The current 6-digit code is required for this action.', 'no_recovery_locked': 'Password reset is unavailable because no recovery code is active.', 'show': 'Show', 'hide': 'Hide',
    },
}


class Translator:
    def __init__(self, resource_dir: Path | None = None):
        self.resource_dir = resource_dir or Path(__file__).resolve().parent.parent
        self.translations = {key: dict(value) for key, value in TEXT.items()}
        self._load_external()
        self.config_path = app_data_dir() / 'settings.json'
        self.language = self._load_language()

    def _load_external(self) -> None:
        path = self.resource_dir / 'more_languages.json'
        if not path.exists():
            return
        try:
            values = json.loads(path.read_text(encoding='utf-8'))
            for code, content in values.items():
                if isinstance(content, dict):
                    self.translations[code] = {**TEXT['en'], **content}
        except Exception:
            return

    def _load_language(self) -> str:
        try:
            value = json.loads(self.config_path.read_text(encoding='utf-8')).get('language', 'hu')
            return value if value in self.translations else 'hu'
        except Exception:
            return 'hu'

    def set_language(self, language: str) -> None:
        if language in self.translations:
            self.language = language
            self.config_path.write_text(json.dumps({'language': language}, ensure_ascii=False), encoding='utf-8')

    def t(self, key: str, **values: object) -> str:
        text = self.translations.get(self.language, {}).get(key, self.translations['en'].get(key, key))
        return text.format(**values)
