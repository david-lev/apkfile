import shutil
import subprocess
import re
from enum import Enum
from typing import Optional, Tuple, Union, List, Iterable


def _get_program_path(program: str) -> str:
    """
    Helper function to get the path of a program.

    Args:
        program: The name of the program.
    Returns:
        The path to the program.
    Raises:
        FileNotFoundError: If the program is not in the PATH.
    """
    program_path = shutil.which(program)
    if program_path is None:
        raise FileNotFoundError
    return program_path


def get_raw_aapt(apk_path: str, aapt_path: Optional[str] = None) -> str:
    """
    Helper function to get the raw output of the aapt command.

    Args:
        apk_path: The path to the apk.
        aapt_path: The path to the aapt executable (If not specified, aapt will be searched in the PATH).
    Returns:
        The raw output of the aapt command.
    Raises:
        FileNotFoundError: If aapt is not installed.
        RuntimeError: If the aapt command failed.
    """
    try:
        return subprocess.run(
            [aapt_path or _get_program_path('aapt'), 'd', 'badging', apk_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=True).stdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.stderr.decode('utf-8'))
    except FileNotFoundError as e:
        raise FileNotFoundError('aapt is not installed') from e


def _get_connected_devices(adb_path: Optional[str] = None) -> Tuple[str]:
    """
    Helper function to get the connected devices using adb.

    Args:
        adb_path: The path to the adb executable (If not specified, adb will be searched in the PATH).
    Returns:
        A tuple of the connected device ids.
    """
    try:
        results = subprocess.run(
            [adb_path or _get_program_path('adb'), 'devices'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=True).stdout.decode('utf-8').strip().split("\n")[1:]
        return tuple(line.split("\t")[0] for line in results if line.endswith('device'))
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.stderr.decode('utf-8'))


def install_apks(
        apks: Union[str, Iterable[str]],
        upgrade: bool = False,
        device_id: Optional[str] = None,
        installer: Optional[str] = None,
        originating_uri: Optional[str] = None,
        adb_path: Optional[str] = None
):
    """
    Helper function to install apks on devices using ``adb``.

    `Android Debug Bridge (ADB) <https://developer.android.com/studio/command-line/adb>`_

    Args:
        apks: The path to the apk or a list of paths to the apks.
        upgrade: Whether to upgrade the app if it is already installed (``INSTALL_FAILED_ALREADY_EXISTS``).
        device_id: The id of the device to install the apk on (If not specified, all connected devices will be used).
        installer: The package name of the app that is performing the installation. (e.g. ``com.android.vending``)
        originating_uri: The URI of the app that is performing the installation.
        adb_path: The path to the adb executable (If not specified, adb will be searched in the ``PATH``).

    Raises:
        FileNotFoundError: If adb is not installed.
        RuntimeError: If the adb command failed.
    """
    adb_path = adb_path or _get_program_path('adb')
    apks = {shutil.os.path.abspath(apk): shutil.os.path.getsize(apk) for apk in ([apks] if isinstance(apks, str) else apks)}
    devices = {device_id: None} if device_id else {device: None for device in _get_connected_devices(adb_path)}
    tmp_path = '/data/local/tmp'
    for device in devices:
        try:
            subprocess.run(
                [adb_path, '-s', device, 'shell', 'mkdir', '-p', tmp_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
            )
            subprocess.run(
                [adb_path, '-s', device, 'push', *apks, tmp_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
            )
            session_id = re.search(r'[0-9]+', subprocess.run(
                [adb_path, '-s', device, 'shell', 'pm', 'install-create',
                 ('-r' if upgrade else ''),  *(['-i', installer] if installer else []),
                 *(['--originating-uri', originating_uri] if originating_uri else []),
                 '-S', str(sum(apks.values()))],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
            ).stdout.decode('utf-8')).group(0)

            for idx, (apk, size) in enumerate(apks.items()):
                basename = shutil.os.path.basename(apk)
                subprocess.run(
                    [adb_path, '-s', device, 'shell', 'pm', 'install-write',
                     '-S', str(size), session_id, str(idx), f'{tmp_path}/{basename}'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
                )
            subprocess.run(
                [adb_path, '-s', device, 'shell', 'pm', 'install-commit', session_id],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to install apk on device {device}: {e.stderr.decode('utf-8')}") from e


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
