import base64
import hashlib
import json
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


SCRYPT_PARAMS = {'length': 32, 'n': 2**14, 'r': 8, 'p': 1}
MASTER_KEY_LEN = 32
NONCE_SIZE = 12


def derive_key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, **SCRYPT_PARAMS).derive(password.encode('utf-8'))


def derive_totp_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode('ascii')).digest()


def aes_encrypt(key: bytes, plaintext: bytes, associated_data: bytes | None = None) -> bytes:
    nonce = secrets.token_bytes(NONCE_SIZE)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, associated_data)


def aes_decrypt(key: bytes, blob: bytes, associated_data: bytes | None = None) -> bytes:
    if len(blob) <= NONCE_SIZE:
        raise ValueError('Invalid encrypted value')
    nonce, ciphertext = blob[:NONCE_SIZE], blob[NONCE_SIZE:]
    return AESGCM(key).decrypt(nonce, ciphertext, associated_data)


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode('ascii')


def unb64(value: str) -> bytes:
    return base64.b64decode(value.encode('ascii'))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def password_wrapper(master_key: bytes, password: str) -> tuple[str, str]:
    salt = secrets.token_bytes(16)
    return b64(salt), b64(aes_encrypt(derive_key(password, salt), master_key))


def unwrap_password(meta: dict, password: str) -> bytes:
    salt = unb64(meta['salt_pwd'])
    return aes_decrypt(derive_key(password, salt), unb64(meta['enc_master_pwd']))
