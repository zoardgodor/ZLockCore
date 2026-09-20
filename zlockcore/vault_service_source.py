import hashlib
import secrets
import shutil
from pathlib import Path

from .config import LEGACY_META, workspace_dir
from .container_v2 import ZLockContainer, create_container
from .crypto import aes_decrypt, aes_encrypt, b64, derive_key, derive_totp_key, password_wrapper, read_json, unb64, unwrap_password, write_json
from .keyring_store import KeyringError, SecretStore
from .totp import generate_secret, provisioning_uri, verify_code


class VaultError(RuntimeError):
    pass


class VaultService:
    def __init__(self):
        self.workspaces: dict[str, Path] = {}

    def is_legacy(self, path: Path) -> bool:
        return path.is_dir()

    def metadata(self, path: Path) -> dict:
        return read_json(path / LEGACY_META) if self.is_legacy(path) else ZLockContainer(path).metadata()

    def _id(self, path: Path) -> str:
        return hashlib.sha256(str(path.absolute()).encode('utf-8')).hexdigest()

    def create(self, path: Path, password: str, description: str = '', recovery: str | None = None) -> bytes:
        master_key = secrets.token_bytes(32)
        salt_pwd, encrypted = password_wrapper(master_key, password)
        metadata = {'format': 2, 'description': description, 'salt_pwd': salt_pwd, 'enc_master_pwd': encrypted, 'recovery_enabled': bool(recovery), 'totp': {'mode': 'disabled'}}
        if recovery:
            self._set_recovery_metadata(metadata, master_key, recovery)
        create_container(path, metadata, master_key)
        return master_key

    def _set_recovery_metadata(self, metadata: dict, master_key: bytes, recovery: str) -> None:
        salt = secrets.token_bytes(16)
        metadata['recovery_enabled'] = True
        metadata['salt_rec'] = b64(salt)
        metadata['enc_master_rec'] = b64(aes_encrypt(derive_key(recovery, salt), master_key))

    def recovery_active(self, path: Path) -> bool:
        metadata = self.metadata(path)
        return bool(metadata.get('recovery_enabled') and metadata.get('salt_rec') and metadata.get('enc_master_rec'))

    def generate_recovery(self, path: Path, master_key: bytes) -> str:
        words = ['river', 'tree', 'stone', 'cloud', 'light', 'key', 'garden', 'window', 'silver', 'mountain', 'paper', 'orange', 'bridge', 'thunder', 'forest', 'planet']
        recovery = ' '.join(secrets.choice(words) for _ in range(24))
        metadata = self.metadata(path)
        self._set_recovery_metadata(metadata, master_key, recovery)
        self.update_metadata(path, metadata)
        return recovery

    def disable_recovery(self, path: Path, master_key: bytes) -> None:
        metadata = self.metadata(path)
        metadata.pop('recovery_enabled', None)
        metadata.pop('salt_rec', None)
        metadata.pop('enc_master_rec', None)
        self.update_metadata(path, metadata)

    def _totp_key(self, path: Path, metadata: dict, code: str) -> bytes:
        config = metadata.get('totp') or {}
        try:
            secret = SecretStore(self._id(path)).load()
        except KeyringError as exc:
            raise VaultError(str(exc)) from exc
        if not verify_code(secret, code, int(config.get('digits', 6)), int(config.get('period', 30))):
            raise VaultError('Invalid TOTP code')
        return aes_decrypt(derive_totp_key(secret), unb64(metadata['enc_master_totp']))

    def totp_config(self, path: Path) -> dict:
        return dict(self.metadata(path).get('totp') or {'mode': 'disabled'})

    def prepare_totp(self, path: Path, mode: str, issuer: str, account: str) -> tuple[dict, str, str]:
        if mode == 'disabled':
            raise VaultError('TOTP mode is disabled')
        config = {'mode': mode, 'issuer': issuer or 'ZLockCore', 'account': account or path.stem, 'digits': 6, 'period': 30, 'algorithm': 'SHA1'}
        secret = generate_secret()
        return config, secret, provisioning_uri(secret, config['account'], config['issuer'])

    def activate_totp(self, path: Path, master_key: bytes, config: dict, secret: str, code: str) -> None:
        if not verify_code(secret, code, int(config.get('digits', 6)), int(config.get('period', 30))):
            raise VaultError('Invalid TOTP activation code')
        store = SecretStore(self._id(path))
        store.save(secret)
        metadata = self.metadata(path)
        metadata['totp'] = config
        metadata['enc_master_totp'] = b64(aes_encrypt(derive_totp_key(secret), master_key))
        self.update_metadata(path, metadata)

    def delete_totp(self, path: Path, code: str) -> None:
        metadata = self.metadata(path)
        config = metadata.get('totp') or {}
        if config.get('mode', 'disabled') == 'disabled':
            return
        try:
            secret = SecretStore(self._id(path)).load()
        except KeyringError as exc:
            raise VaultError(str(exc)) from exc
        if not verify_code(secret, code, int(config.get('digits', 6)), int(config.get('period', 30))):
            raise VaultError('Invalid TOTP deletion code')
        SecretStore(self._id(path)).delete()
        metadata.pop('enc_master_totp', None)
        metadata['totp'] = {'mode': 'disabled'}
        self.update_metadata(path, metadata)

    def unlock(self, path: Path, password: str | None, code: str | None) -> bytes:
        metadata = self.metadata(path)
        mode = (metadata.get('totp') or {}).get('mode', 'disabled')
        password_key = None
        code_key = None
        if password:
            try:
                password_key = unwrap_password(metadata, password)
            except Exception:
                password_key = None
        if code and mode != 'disabled':
            try:
                code_key = self._totp_key(path, metadata, code)
            except Exception:
                code_key = None
        if mode in {'disabled', 'password_only'}:
            master = password_key
        elif mode == 'totp_or_password':
            master = password_key or code_key
        elif mode == 'password_and_totp':
            master = password_key if password_key is not None and password_key == code_key else None
        else:
            master = password_key
        if master is None:
            raise VaultError('Invalid credentials')
        return master

    def recover_master(self, path: Path, recovery: str) -> bytes:
        metadata = self.metadata(path)
        if not self.recovery_active(path):
            raise VaultError('Recovery is not configured')
        return aes_decrypt(derive_key(recovery, unb64(metadata['salt_rec'])), unb64(metadata['enc_master_rec']))

    def update_metadata(self, path: Path, metadata: dict) -> None:
        if self.is_legacy(path):
            write_json(path / LEGACY_META, metadata)
        else:
            ZLockContainer(path).update_metadata(metadata)

    def change_password(self, path: Path, master_key: bytes, password: str) -> None:
        metadata = self.metadata(path)
        metadata['salt_pwd'], metadata['enc_master_pwd'] = password_wrapper(master_key, password)
        self.update_metadata(path, metadata)

    def workspace(self, path: Path) -> Path:
        key = self._id(path)
        self.workspaces.setdefault(key, workspace_dir() / key)
        return self.workspaces[key]

    def extract(self, path: Path, master_key: bytes) -> Path:
        destination = self.workspace(path)
        if self.is_legacy(path):
            from .legacy import decrypt_all_to_plain
            decrypt_all_to_plain(path, master_key, destination)
        else:
            ZLockContainer(path).extract(master_key, destination)
        return destination

    def pack(self, path: Path, master_key: bytes) -> None:
        source = self.workspace(path)
        if self.is_legacy(path):
            from .legacy import encrypt_plain_back_and_cleanup
            encrypt_plain_back_and_cleanup(path, master_key, source)
        else:
            ZLockContainer(path).pack(master_key, source)
        shutil.rmtree(source, ignore_errors=True)
