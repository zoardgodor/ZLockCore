import io
import json
import secrets
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from .crypto import aes_decrypt, aes_encrypt, b64, unb64


MAGIC = b'ZLOCK2\x00'


class ContainerError(RuntimeError):
    pass


def _pack_directory(source: Path, master_key: bytes) -> bytes:
    manifest = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        if source.exists():
            for file_path in sorted(source.rglob('*')):
                if not file_path.is_file():
                    continue
                relative = file_path.relative_to(source).as_posix()
                object_name = f'objects/{len(manifest):016x}.bin'
                file_key = secrets.token_bytes(32)
                archive.writestr(object_name, aes_encrypt(file_key, file_path.read_bytes()))
                manifest.append({'path': relative, 'object': object_name, 'enc_file_key': b64(aes_encrypt(master_key, file_key))})
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False).encode('utf-8'))
    return buffer.getvalue()


class ZLockContainer:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _read(self) -> tuple[dict, bytes]:
        with self.path.open('rb') as handle:
            if handle.read(len(MAGIC)) != MAGIC:
                raise ContainerError('Invalid ZLock container')
            size = int.from_bytes(handle.read(4), 'big')
            try:
                metadata = json.loads(handle.read(size).decode('utf-8'))
            except Exception as exc:
                raise ContainerError('Invalid ZLock metadata') from exc
            return metadata, handle.read()

    def metadata(self) -> dict:
        return self._read()[0]

    def _write(self, metadata: dict, payload: bytes) -> None:
        encoded = json.dumps(metadata, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        temporary = self.path.with_suffix(self.path.suffix + '.tmp')
        with temporary.open('wb') as handle:
            handle.write(MAGIC)
            handle.write(len(encoded).to_bytes(4, 'big'))
            handle.write(encoded)
            handle.write(payload)
        temporary.replace(self.path)

    def create(self, metadata: dict, master_key: bytes) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write(metadata, aes_encrypt(master_key, _pack_directory(self.path.parent / (self.path.stem + '.empty'), master_key)))

    def update_metadata(self, metadata: dict) -> None:
        _, payload = self._read()
        self._write(metadata, payload)

    def extract(self, master_key: bytes, destination: Path) -> None:
        _, payload = self._read()
        try:
            archive = zipfile.ZipFile(io.BytesIO(aes_decrypt(master_key, payload)))
            manifest = json.loads(archive.read('manifest.json').decode('utf-8'))
        except Exception as exc:
            raise ContainerError('The container could not be decrypted') from exc
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True, exist_ok=True)
        for item in manifest:
            relative = PurePosixPath(item['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ContainerError('Container contains an invalid path')
            output = destination.joinpath(*relative.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            file_key = aes_decrypt(master_key, unb64(item['enc_file_key']))
            output.write_bytes(aes_decrypt(file_key, archive.read(item['object'])))

    def pack(self, master_key: bytes, source: Path) -> None:
        metadata, _ = self._read()
        self._write(metadata, aes_encrypt(master_key, _pack_directory(source, master_key)))


def create_container(path: Path, metadata: dict, master_key: bytes) -> None:
    ZLockContainer(path).create(metadata, master_key)
