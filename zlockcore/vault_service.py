from .vault_service_source import *


class VaultService(VaultService):
    def set_totp_mode(self, path: Path, mode: str) -> None:
        metadata = self.metadata(path)
        config = metadata.get('totp') or {}
        if config.get('mode', 'disabled') == 'disabled':
            raise VaultError('TOTP is not active')
        if mode == 'totp_only':
            raise VaultError('TOTP-only unlock is not supported')
        config['mode'] = mode
        metadata['totp'] = config
        self.update_metadata(path, metadata)
