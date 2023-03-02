import re
import subprocess
import shutil
from dataclasses import dataclass, asdict, fields, field
from enum import Enum
from typing import Optional, Dict, Union, Tuple

__all__ = [
    'get_apk_info',
    'ApkInfo',
    'get_raw_aapt',
    'Abi',
    'InstallLocation'
]


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

    def __repr__(self):
        return f'Abi.{self.name}'


@dataclass(frozen=True)
class ApkInfo:
    """
    Represents the information of an Android app.

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
    """
    package_name: str = field(default=r'package: name=\'([^\']+)\'')
    version_code: int = field(default=r'versionCode=\'([^\']+)\'')
    version_name: Optional[str] = field(default=r'versionName=\'([^\']+)\'')
    min_sdk_version: Optional[int] = field(default=r'sdkVersion:\'([^\']+)\'')
    target_sdk_version: Optional[int] = field(default=r'targetSdkVersion:\'([^\']+)\'')
    install_location: InstallLocation = field(default=r'install-location:\'([^\']+)\'')
    labels: Dict[str, str] = field(default=r'application-label-([a-z]{2}):\'' + r'([^\']+)\'')
    permissions: Tuple[str] = field(default=r'uses-permission: name=\'([^\']+)\'')
    libraries: Tuple[str] = field(default=r'uses-library(?:-not-required)?:\'([^\']+)\'')
    features: Tuple[str] = field(default=r'uses-feature(?:-not-required)?: name=\'([^\']+)\'')
    launchable_activity: Optional[str] = field(default=r'launchable-activity: name=\'([^\']+)\'')
    supported_screens: Tuple[str] = field(default=r'supports-screens: \'([a-z\'\s]+)\'')
    supports_any_density: bool = field(default=r'supports-any-density: \'([^\']+)\'')
    langs: Tuple[str] = field(default=r'locales: \'([a-zA-Z\'\s\-\_]+)\'')
    densities: Tuple[str] = field(default=r'densities: \'([0-9\'\s]+)\'')
    abis: Tuple[Abi] = field(default=r'native-code: \'([^\']+)\'')
    icons: Dict[int, str] = field(default=r'application-icon-([0-9]+):\'' + r'([^\']+)\'')
    split_name: Optional[str] = field(default=r'split=\'([^\']+)\'')

    @property
    def is_split(self) -> bool:
        """Check if the apk is a split apk."""
        return self.split_name is not None

    @property
    def is_support_any_abi(self) -> bool:
        """Check if the apk supports any abi."""
        return not self.abis or all(abi in self.abis for abi in Abi.all())


def get_apk_info(apk_path: str, as_dict: bool = False, aapt_path: Optional[str] = None) -> Union[ApkInfo, Dict]:
    """
    Get apk info.

    Args:
        apk_path: Path to the apk file. (e.g. '/path/to/app.apk')
        as_dict: Return a dict instead of ApkInfo object (default: False).
        aapt_path: Path to aapt binary (if not in PATH).

    Returns:
        ApkInfo object or dict if `as_dict` is True.

    Raises:
        FileNotFoundError: If aapt binary or apk file not found.
        FileExistsError: If apk file is not a valid apk file.
        RuntimeError: If aapt binary failed to run.
    """
    try:
        raw = get_raw_aapt(apk_path, aapt_path)
    except RuntimeError as e:
        err_msg = str(e)
        if 'Invalid file' in err_msg:
            raise FileExistsError(err_msg)
        elif 'is neither a directory nor file' in err_msg:
            raise FileNotFoundError(err_msg)
        raise
    data = {f.name: re.findall(str(f.default), raw) for f in fields(ApkInfo)}
    info = ApkInfo(
        package_name=data['package_name'][0],
        version_code=int(data['version_code'][0]),
        version_name=(data.get('version_name') or (None,))[0],
        min_sdk_version=int((data.get('min_sdk_version') or (0,))[0]) or None,
        target_sdk_version=int((data.get('target_sdk_version') or (0,))[0]) or None,
        install_location=InstallLocation(data.get('install_location') or ('auto',)[0]),
        labels={lang: label for lang, label in data.get('labels', {})},
        permissions=tuple(data.get('permissions', ())),
        libraries=tuple(data.get('libraries', ())),
        features=tuple(data.get('features', ())),
        launchable_activity=(data.get('launchable_activity') or (None,))[0],
        supported_screens=tuple(str(s) for s in re.split(r"'\s'", data['supports_screens'][0])) if
        data.get('supports_screens') else (),
        supports_any_density=(data.get('supports_any_density') or (None,))[0] == 'true',
        langs=tuple(lang.strip() for lang in re.split(r"'\s'", data['langs'][0]) if
                    re.match(r'^[A-Za-z\-]+$', lang)) if data.get('langs') else (),
        densities=tuple(str(d) for d in re.split(r"'\s'", data['densities'][0])) if data.get('densities') else (),
        abis=tuple(Abi(abi) for abi in re.split(r"'\s'", data['abis'][0])) if data.get('abis') else Abi.all(),
        icons={int(size): icon for size, icon in data.get('icons', {})},
        split_name=data.get('split_name') or None,
    )

    return info if not as_dict else asdict(info)
