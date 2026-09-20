import json
import secrets
import shutil
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import LEGACY_STORAGE
from .crypto import MASTER_KEY_LEN, NONCE_SIZE, aes_decrypt, aes_encrypt, b64, unb64


def decrypt_all_to_plain(vault_root: Path, master_key: bytes, destination: Path) -> None:
    storage = vault_root / LEGACY_STORAGE
    destination.mkdir(parents=True, exist_ok=True)
    if not storage.exists():
        return
    for meta_path in storage.glob('*.meta.json'):
        try:
            metadata = json.loads(meta_path.read_text(encoding='utf-8'))
            source = storage / meta_path.name.replace('.meta.json', '.cbox')
            file_key = aes_decrypt(master_key, unb64(metadata['enc_file_key']))
            data = source.read_bytes()
            name = aes_decrypt(master_key, unb64(metadata['enc_name'])).decode('utf-8')
            output = destination / name
            suffix = 1
            while output.exists():
                output = destination / f'{Path(name).stem}_{suffix}{Path(name).suffix}'
                suffix += 1
            output.write_bytes(AESGCM(file_key).decrypt(data[:NONCE_SIZE], data[NONCE_SIZE:], None))
        except Exception:
            continue


def _store(vault_root: Path, master_key: bytes, source: Path) -> None:
    storage = vault_root / LEGACY_STORAGE
    storage.mkdir(parents=True, exist_ok=True)
    identifier = secrets.token_hex(12)
    file_key = secrets.token_bytes(MASTER_KEY_LEN)
    nonce = secrets.token_bytes(NONCE_SIZE)
    (storage / f'{identifier}.cbox').write_bytes(nonce + AESGCM(file_key).encrypt(nonce, source.read_bytes(), None))
    metadata = {'enc_file_key': b64(aes_encrypt(master_key, file_key)), 'enc_name': b64(aes_encrypt(master_key, source.name.encode('utf-8')))}
    (storage / f'{identifier}.meta.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')


def encrypt_plain_back_and_cleanup(vault_root: Path, master_key: bytes, source: Path) -> None:
    if not source.exists():
        return
    for child in list(source.iterdir()):
        if child.is_file():
            _store(vault_root, master_key, child)
        elif child.is_dir():
            encrypt_plain_back_and_cleanup(vault_root, master_key, child)
    shutil.rmtree(source, ignore_errors=True)
