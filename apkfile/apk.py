import hashlib
import os
import shutil
import subprocess
import re
from zipfile import ZipFile
from enum import Enum
from typing import Optional, Tuple, Union, Iterable, Dict, Any


__all__ = [
    'ApkFile',
    'install_apks',
    'get_raw_aapt',
    'Abi',
    'InstallLocation'
]


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
        check: bool = True,
        upgrade: bool = False,
        device_id: Optional[str] = None,
        installer: Optional[str] = None,
        originating_uri: Optional[str] = None,
        adb_path: Optional[str] = None,
        aapt_path: Optional[str] = None
):
    """
    Install apk(s) on a device using `adb <https://developer.android.com/studio/command-line/adb>`_.

    This function will take some time to run, depending on the size of the apk(s) and the speed of the device.

    Args:
        apks: The path to the apk or a list of paths to the apks.
        check: Check if the app is compatible with the device (abi, minSdkVersion, etc.).
        upgrade: Whether to upgrade the app if it is already installed (``INSTALL_FAILED_ALREADY_EXISTS``).
        device_id: The id of the device to install the apk on (If not specified, all connected devices will be used).
        installer: The package name of the app that is performing the installation. (e.g. ``com.android.vending``)
        originating_uri: The URI of the app that is performing the installation.
        adb_path: The path to the adb executable (If not specified, adb will be searched in the ``PATH``).
        aapt_path: The path to the aapt executable (If check is ``True``. If not specified, aapt will be searched in the ``PATH``).

    Raises:
        FileNotFoundError: If adb is not installed.
        RuntimeError: If the adb command failed.
    """
    adb_path = adb_path or _get_program_path('adb')
    devices = (device_id,) if device_id else _get_connected_devices(adb_path=adb_path)
    spargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE, 'check': True}
    for device in devices:
        cmd_args = (adb_path, '-s', device)
        tmp_path = subprocess.run(
            [*cmd_args, 'shell', 'mktemp', '-d', '--tmpdir=/data/local/tmp'], **spargs
        ).stdout.decode('utf-8').strip()

        if check:
            device_abis = (Abi(abi) for abi in subprocess.run(
                [*cmd_args, 'shell', 'getprop', 'ro.product.cpu.abilist'], **spargs
            ).stdout.decode('utf-8').strip().split(','))
            device_sdk = int(subprocess.run(
                [*cmd_args, 'shell', 'getprop', 'ro.build.version.sdk'], **spargs
            ).stdout.decode('utf-8').strip())
            apk_objects = [ApkFile(path=apk, aapt_path=aapt_path) for apk in ([apks] if isinstance(apks, str) else apks)]
            apks = {}
            for apk in apk_objects:
                if (apk.min_sdk_version is None or apk.min_sdk_version <= device_sdk) and \
                     (not apk.abis or
                      any(device_abi.is_compatible_with(apk_abi) for apk_abi in apk.abis for device_abi in device_abis)):
                    apks[shutil.os.path.abspath(apk.path)] = shutil.os.path.getsize(apk.path)
        else:
            apks = {
                shutil.os.path.abspath(apk): shutil.os.path.getsize(apk)
                for apk in ([apks] if isinstance(apks, str) else apks)
            }

        try:
            subprocess.run([*cmd_args, 'push', *apks, tmp_path], **spargs)
            session_id = re.search(r'[0-9]+', subprocess.run(
                [*cmd_args, 'shell', 'pm', 'install-create',
                 ('-r' if upgrade else ''), *(['-i', installer] if installer else []),
                 *(['--originating-uri', originating_uri] if originating_uri else []),
                 '-S', str(sum(apks.values()))], **spargs
            ).stdout.decode('utf-8')).group(0)

            for idx, (apk, size) in enumerate(apks.items()):
                basename = shutil.os.path.basename(apk)
                subprocess.run(
                    [*cmd_args, 'shell', 'pm', 'install-write', '-S',
                     str(size), session_id, str(idx), f'{tmp_path}/{basename}'], **spargs
                )
            subprocess.run([*cmd_args, 'shell', 'pm', 'install-commit', session_id], **spargs)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to install apk on device {device}: {e.stderr.decode('utf-8')}") from e
        finally:
            subprocess.run([*cmd_args, 'shell', 'rm', '-rf', tmp_path], **spargs)


class InstallLocation(Enum):
    """
    Where the application can be installed on external storage, internal only or auto.

    See `Android documentation <https://developer.android.com/reference/android/content/pm/PackageInfo.html#installLocation>`_.

    Attributes:
        AUTO: Let the system decide where to install the app.
        INTERNAL_ONLY: Install the app on internal storage only.
        PREFER_EXTERNAL: Prefer external storage.
    """
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
    """
    Android supported ABIs.

    See `Android documentation <https://developer.android.com/ndk/guides/abis>`_.

    Attributes:
        ARM: armeabi
        ARM7: armeabi-v7a
        ARM64: arm64-v8a
        X86: x86
        X86_64: x86_64
        UNKNOWN: Unknown ABI
    """
    ARM = 'armeabi'
    ARM7 = 'armeabi-v7a'
    ARM64 = 'arm64-v8a'
    X86 = 'x86'
    X86_64 = 'x86_64'
    UNKNOWN = 'unknown'

    def is_compatible_with(self, other: 'Abi') -> bool:
        """Returns whether this ABI is compatible with the other ABI."""
        if self == other:
            return True
        return other in _compatibility_map[self]

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


_compatibility_map = {
    Abi.X86_64: frozenset({Abi.X86, Abi.ARM64,Abi.ARM7, Abi.ARM}),
    Abi.X86: frozenset({Abi.ARM64, Abi.ARM7, Abi.ARM}),
    Abi.ARM64: frozenset({Abi.ARM7, Abi.ARM}),
    Abi.ARM7: frozenset({Abi.ARM}),
    Abi.ARM: frozenset(),
    Abi.UNKNOWN: frozenset(),
}


_extraction_patterns = {
    'package_name': r'package: name=\'([^\']+)\'',
    'version_code': r'versionCode=\'([^\']+)\'',
    'version_name': r'versionName=\'([^\']+)\'',
    'min_sdk_version': r'sdkVersion:\'([^\']+)\'',
    'target_sdk_version': r'targetSdkVersion:\'([^\']+)\'',
    'install_location': r'install-location:\'([^\']+)\'',
    'labels': r'application-label-([a-z]{2}):\'' + r'([^\']+)\'',
    'permissions': r'uses-permission: name=\'([^\']+)\'',
    'libraries': r'uses-library(?:-not-required)?:\'([^\']+)\'',
    'features': r'uses-feature(?:-not-required)?: name=\'([^\']+)\'',
    'launchable_activity': r'launchable-activity: name=\'([^\']+)\'',
    'supported_screens': r'supports-screens: \'([a-z\'\s]+)\'',
    'supports_any_density': r'supports-any-density: \'([^\']+)\'',
    'langs': r'locales: \'([a-zA-Z\'\s\-\_]+)\'',
    'densities': r'densities: \'([0-9\'\s]+)\'',
    'abis': r'native-code: \'([^\']+)\'',
    'icons': r'application-icon-([0-9]+):\'' + r'([^\']+)\'',
    'split_name': r'split=\'([^\']+)\'',
}


class _BaseApkFile:
    package_name: str
    version_code: int
    version_name: Optional[str]
    min_sdk_version: Optional[int]
    target_sdk_version: Optional[int]
    install_location: InstallLocation
    labels: Dict[str, str]
    permissions: Tuple[str]
    libraries: Tuple[str]
    features: Tuple[str]
    launchable_activity: Optional[str]
    supported_screens: Tuple[str]
    supports_any_density: bool
    langs: Tuple[str]
    densities: Tuple[str]
    abis: Tuple[Abi]
    icons: Dict[int, str]
    split_name: Optional[str]
    path: Union[str, os.PathLike]
    size: int
    md5: str

    @property
    def size(self) -> int:
        """Get the apk file size in bytes."""
        return os.path.getsize(self.path)

    @property
    def md5(self) -> str:
        """Get the apk file md5."""
        return hashlib.md5(open(self.path, 'rb').read()).hexdigest()

    def as_zip_file(self) -> ZipFile:
        """Get the apk file as a zip file."""
        return ZipFile(self.path)

    def install(
            self,
            check: bool = True,
            upgrade: bool = False,
            device_id: Optional[str] = None,
            installer: Optional[str] = None,
            originating_uri: Optional[str] = None,
            adb_path: Optional[str] = None,
            aapt_path: Optional[str] = None
    ):
        """
        Install the apk on the device.

        Args:
            check: Check if the app is compatible with the device (abi, minSdkVersion, etc).
            upgrade: Whether to upgrade the app if it is already installed (``INSTALL_FAILED_ALREADY_EXISTS``).
            device_id: The id of the device to install the apk on (If not specified, all connected devices will be used).
            installer: The package name of the app that is performing the installation. (e.g. ``com.android.vending``)
            originating_uri: The URI of the app that is performing the installation.
            adb_path: The path to the adb executable (If not specified, adb will be searched in the ``PATH``).
            aapt_path: The path to the aapt executable (If check is ``True``. If not specified, aapt will be searched in the ``PATH``).

        Raises:
            FileNotFoundError: If adb is not installed.
            RuntimeError: If the adb command failed.
        """
        install_apks(
            apks=self.path,
            check=check,
            upgrade=upgrade,
            device_id=device_id,
            installer=installer,
            originating_uri=originating_uri,
            adb_path=adb_path
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(pkg='{self.package_name}', version={self.version_code})"


class ApkFile(_BaseApkFile):
    """
    Represents the information of an Android app.

    An APK file is an app created for Android, Google's mobile operating system. Some apps come pre-installed on Android
    devices, while other apps can be downloaded from Google Play. Apps downloaded from Google Play are automatically
    installed on your device, while those downloaded from other sources must be installed manually.
        `For more information ↗️ <https://fileinfo.com/extension/apk>`_.
        `APK in Wikipedia ↗️ <https://en.wikipedia.org/wiki/Apk_(file_format)>`_.

    Attributes:
        package_name: The package name of an Android app uniquely identifies the app on the device, in Google Play Store, and in supported third-party Android stores.
            `↗️ <https://support.google.com/admob/answer/9972781>`_
        version_code: The version code is an incremental integer value that represents the version of the application code.
            `↗️ <https://developer.android.com/studio/publish/versioning#appversioning>`_
        version_name: A string value that represents the release version of the application code.
            `↗️ <https://developer.android.com/studio/publish/versioning#appversioning>`_
        min_sdk_version: The minimum version of the Android platform on which the app will run.
            `↗️ <https://developer.android.com/studio/publish/versioning#minsdkversion>`_
        target_sdk_version: The API level on which the app is designed to run.
            `↗️ <https://developer.android.com/studio/publish/versioning#minsdkversion>`_
        install_location: Where the application can be installed on external storage, internal only or auto.
            `↗️ <https://developer.android.com/guide/topics/data/install-location>`_
        labels: A user-readable labels for the application.
            `↗️ <https://developer.android.com/guide/topics/manifest/application-element#:~:text=or%20getLargeMemoryClass().-,android%3Alabel,-A%20user%2Dreadable>`_
        permissions: A system permission that the user must grant in order for the app to operate correctly.
            `↗️ <https://developer.android.com/guide/topics/manifest/uses-permission-element>`_
        libraries: A shared libraries that the application must be linked against.
            `↗️ <https://developer.android.com/guide/topics/manifest/uses-library-element>`_
        features: A hardware or software feature that is used by the application.
            `↗️ <https://developer.android.com/guide/topics/manifest/uses-feature-element>`_
        supported_screens: Screen sizes the application supports.
            `↗️ <https://developer.android.com/guide/topics/manifest/supports-screens-element>`_
        launchable_activity: The main activity that can be launched.
            `↗️ <https://developer.android.com/reference/android/app/Activity>`_
        supports_any_density: Indicates whether the application includes resources to accommodate any screen density.
            `↗️ <https://developer.android.com/guide/topics/manifest/supports-screens-element#any:~:text=API%20level%209.-,android%3AanyDensity,-Indicates%20whether%20the>`_
        langs: Supported languages.
            `↗️ <https://developer.android.com/guide/topics/resources/localization>`_
        densities: Supported pixel densities.
            `↗️ <https://developer.android.com/guide/topics/large-screens/support-different-screen-sizes>`_
        abis: Android supported ABIs.
            `↗️ <https://developer.android.com/ndk/guides/abis>`_
        icons: Path's to the app icons.
            `↗️ <https://developer.android.com/guide/topics/resources/providing-resources>`_
        split_name: The name of the split apk (if is_split).
            `↗️ <https://developer.android.com/studio/build/configure-apk-splits.html>`_

        is_split: Whether the apk is a split apk.
        is_universal: Whether the apk is a universal apk (supports all ABIs).
        path: The path to the apk file.
        size: The size of the apk file.
        md5: The MD5 hash of the apk file.
    """
    is_split: bool
    is_universal: bool

    def __init__(
            self,
            path: Union[str, os.PathLike],
            aapt_path: Optional[Union[str, os.PathLike]] = None
    ) -> None:
        """
        Initialize an ApkFile instance.

        Args:
            path: Path to the apk file. (e.g. '/path/to/app.apk')
            aapt_path: Path to aapt binary (if not in PATH).

        Raises:
            FileNotFoundError: If aapt binary or apk file not found.
            FileExistsError: If apk file is not a valid apk file.
            RuntimeError: If aapt binary failed to run.
        """
        if isinstance(path, os.PathLike):
            path = os.fspath(path)
        self.path = path
        try:
            raw = get_raw_aapt(apk_path=self.path, aapt_path=aapt_path)
        except RuntimeError as e:
            err_msg = str(e)
            if any(x in err_msg for x in ('Invalid file', 'AndroidManifest.xml')):
                raise FileExistsError(f"'{self.path}' is not a valid apk file.\nAAPT error: {err_msg}")
            elif 'is neither a directory nor file' in err_msg:
                raise FileNotFoundError(err_msg)
            raise
        self._raw = raw
        data = {name: re.findall(pattern, raw) for name, pattern in _extraction_patterns.items()}

        self.package_name = data['package_name'][0]
        self.version_code = int(data['version_code'][0])
        self.version_name = (data.get('version_name') or (None,))[0]
        self.min_sdk_version = int((data.get('min_sdk_version') or (0,))[0]) or None
        self.target_sdk_version = int((data.get('target_sdk_version') or (0,))[0]) or None
        self.install_location = InstallLocation(data.get('install_location') or ('auto',)[0])
        self.labels = {lang: label for lang, label in data.get('labels', {})}
        self.permissions = tuple(data.get('permissions', ()))
        self.libraries = tuple(data.get('libraries', ()))
        self.features = tuple(data.get('features', ()))
        self.launchable_activity = (data.get('launchable_activity') or (None,))[0]
        self.supported_screens = tuple(str(s) for s in re.split(r"'\s'", data['supports_screens'][0])) if \
            data.get('supports_screens') else ()
        self.supports_any_density = (data.get('supports_any_density') or (None,))[0] == 'true'
        self.langs = tuple(lang.strip() for lang in re.split(r"'\s'", data['langs'][0]) if
                           re.match(r'^[A-Za-z\-]+$', lang)) if data.get('langs') else ()
        self.densities = tuple(str(d) for d in re.split(r"'\s'", data['densities'][0])) if data.get('densities') else ()
        self.split_name = data.get('split_name')[0] if data.get('split_name') else None
        self.abis = tuple(Abi(abi) for abi in re.split(r"'\s'", data['abis'][0])) if data.get('abis') else ()
        self.icons = {int(size): icon for size, icon in data.get('icons', {})}

    @property
    def is_split(self) -> bool:
        """Check if the apk is a split apk."""
        return self.split_name is not None if hasattr(self, 'split_name') else False

    @property
    def is_universal(self) -> bool:
        """Check if the apk is a universal apk."""
        return len(self.abis) == 0 or all(abi in self.abis for abi in Abi.all())

    def extract(self, path: str, members: Optional[Iterable[str]] = None) -> None:
        """
        Extract files from the apk to a directory.

        >>> apk_file.extract(path='out', members=['AndroidManifest.xml'])

        Args:
            path: Path to the directory to extract to.
            members: An optional list of names to extract. If not provided, all files will be extracted.
        """
        self.as_zip_file().extractall(path=path, members=members)

    def as_dict(self) -> Dict[str, Any]:
        return {
            k: v.as_dict() if hasattr(v, 'as_dict') else v
            for k, v in self.__dict__.items() if not k.startswith('_')
        }