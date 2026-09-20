import hashlib

import keyring


class KeyringError(RuntimeError):
    pass


class SecretStore:
    service = 'ZLockCore'

    def __init__(self, vault_id: str):
        self.vault_id = vault_id
        self.username = hashlib.sha256(vault_id.encode('utf-8')).hexdigest()

    def save(self, secret: str) -> None:
        try:
            keyring.set_password(self.service, self.username, secret)
            if keyring.get_password(self.service, self.username) != secret:
                raise KeyringError('The operating system keyring did not confirm the secret')
        except Exception as exc:
            if isinstance(exc, KeyringError):
                raise
            raise KeyringError(f'Operating system keyring is unavailable: {exc}') from exc

    def load(self) -> str:
        try:
            secret = keyring.get_password(self.service, self.username)
        except Exception as exc:
            raise KeyringError(f'Operating system keyring is unavailable: {exc}') from exc
        if not secret:
            raise KeyringError('No TOTP secret is stored in the operating system keyring')
        return secret

    def delete(self) -> None:
        try:
            keyring.delete_password(self.service, self.username)
        except keyring.errors.PasswordDeleteError:
            return
        except Exception as exc:
            raise KeyringError(f'Operating system keyring is unavailable: {exc}') from exc
