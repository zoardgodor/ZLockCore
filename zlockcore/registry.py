import json
from pathlib import Path

from .config import legacy_registry_path, registry_path


class VaultRegistry:
    def __init__(self):
        self.path = registry_path()
        self.vaults = self._load()

    def _load(self) -> dict[str, str]:
        candidates = [self.path, legacy_registry_path()]
        for candidate in candidates:
            if not candidate.exists():
                continue
            try:
                value = json.loads(candidate.read_text(encoding='utf-8'))
                if isinstance(value, dict):
                    return {str(key): str(path) for key, path in value.items()}
            except Exception:
                continue
        return {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.vaults, indent=2, ensure_ascii=False), encoding='utf-8')
        temporary.replace(self.path)

    def add(self, name: str, path: Path) -> None:
        self.vaults[name] = str(path)
        self.save()

    def remove(self, name: str) -> None:
        self.vaults.pop(name, None)
        self.save()
