import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MountPoint:
    path: Path
    drive: str | None = None
    virtual: bool = False


class MountManager:
    def _subst_drives(self) -> set[str]:
        """Return drive letters already assigned by Windows SUBST."""
        result = subprocess.run(['subst'], check=False, capture_output=True, text=True)
        output = f'{result.stdout}\n{result.stderr}'
        return {
            f'{match.group(1).upper()}:'
            for match in re.finditer(r'(?m)^\s*([A-Za-z]):\\:', output)
        }

    def mount(self, source: Path, name: str) -> MountPoint:
        if platform.system() == 'Windows':
            subst_drives = self._subst_drives()
            for letter in 'ZYXWVUTSRQPONMLKJIHGFEDCBA':
                drive = f'{letter}:'
                if drive in subst_drives or Path(f'{drive}\\').exists():
                    continue
                try:
                    subprocess.run(['subst', drive, str(source)], check=True, capture_output=True)
                    return MountPoint(Path(f'{drive}\\'), drive, False)
                except (OSError, subprocess.CalledProcessError):
                    # The drive may have become occupied between the checks.
                    # Try the next candidate instead of aborting the unlock.
                    continue
        return MountPoint(source, None, True)

    def unmount(self, mount: MountPoint | None) -> None:
        if not mount:
            return
        if mount.drive and platform.system() == 'Windows':
            subprocess.run(['subst', mount.drive, '/d'], check=False, capture_output=True)

