import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')


def _decode_secret(secret: str) -> bytes:
    normalized = secret.replace(' ', '').upper()
    return base64.b32decode(normalized + '=' * (-len(normalized) % 8))


def code_at(secret: str, timestamp: int | None = None, digits: int = 6, period: int = 30) -> str:
    counter = int((time.time() if timestamp is None else timestamp) // period)
    digest = hmac.new(_decode_secret(secret), struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10**digits)).zfill(digits)


def verify_code(secret: str, code: str, digits: int = 6, period: int = 30, window: int = 1, timestamp: int | None = None) -> bool:
    if not code.isdigit() or len(code) != digits:
        return False
    now = int(time.time() if timestamp is None else timestamp)
    return any(hmac.compare_digest(code, code_at(secret, now + shift * period, digits, period)) for shift in range(-window, window + 1))


def provisioning_uri(secret: str, account: str, issuer: str, digits: int = 6, period: int = 30) -> str:
    label = f'{issuer}:{account}'
    return f'otpauth://totp/{quote(label)}?secret={quote(secret)}&issuer={quote(issuer)}&algorithm=SHA1&digits={digits}&period={period}'
