import shutil
import subprocess
from enum import Enum
from typing import Optional, Tuple


def get_aapt_path() -> str:
    """Helper function to get the path of aapt."""
    aapt_path = shutil.which('aapt')
    if aapt_path is None:
        raise FileNotFoundError('aapt not found! see https://github.com/david-lev/aapyt#install-aapt')
    return aapt_path


def get_raw_aapt(apk_path: str, aapt_path: Optional[str] = None) -> str:
    """Helper function to get the raw output of aapt."""
    try:
        return subprocess.run(
            [aapt_path or get_aapt_path(), 'd', 'badging', apk_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=True).stdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.stderr.decode('utf-8'))


class InstallLocation(Enum):
    """Where the application can be installed on external storage, internal only or auto."""
    AUTO = 'auto'
    INTERNAL_ONLY = 'internalOnly'
    PREFER_EXTERNAL = 'preferExternal'

    @classmethod
    def _missing_(cls, value):
        return cls.AUTO

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        return f'InstallLocation.{self.name}'


class Abi(Enum):
    """Android supported ABIs."""
    ARM = 'armeabi'
    ARM7 = 'armeabi-v7a'
    ARM64 = 'arm64-v8a'
    X86 = 'x86'
    X86_64 = 'x86_64'
    UNKNOWN = 'unknown'

    @classmethod
    def all(cls) -> Tuple['Abi']:
        """Returns all the supported ABIs."""
        return tuple(a for a in cls if a != cls.UNKNOWN)

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        return f'Abi.{self.name}'
