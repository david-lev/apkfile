import hashlib
import os
import re
import subprocess
from typing import Optional, Dict, Tuple, Iterable, Any
from zipfile import ZipFile
from aapyt.utils import Abi, InstallLocation, get_raw_aapt

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


class ApkFile:
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

    Methods:
        as_zip_file: Returns the apk as a ZipFile.
        extract: Extracts files from the apk.
        install: Installs the apk with adb.
    """
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
    is_split: bool
    is_universal: bool
    path: str
    size: int
    md5: str

    def __init__(self, apk_path: str, aapt_path: Optional[str] = None):
        """
        Initialize an ApkFile instance.

        Args:
            apk_path: Path to the apk file. (e.g. '/path/to/app.apk')
            aapt_path: Path to aapt binary (if not in PATH).

        Raises:
            FileNotFoundError: If aapt binary or apk file not found.
            FileExistsError: If apk file is not a valid apk file.
            RuntimeError: If aapt binary failed to run.
        """
        self._path = apk_path
        try:
            raw = get_raw_aapt(apk_path=self._path, aapt_path=aapt_path)
        except RuntimeError as e:
            err_msg = str(e)
            if 'Invalid file' in err_msg:
                raise FileExistsError(err_msg)
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
    def path(self) -> str:
        """Get the apk path."""
        return self._path

    @property
    def is_split(self) -> bool:
        """Check if the apk is a split apk."""
        return self.split_name is not None

    @property
    def is_universal(self) -> bool:
        """Check if the apk is a universal apk."""
        return len(self.abis) == 0 or all(abi in self.abis for abi in Abi.all())

    @property
    def size(self) -> int:
        """Get the apk file size in bytes."""
        return os.path.getsize(self.path)

    @property
    def md5(self) -> str:
        """Get the apk file md5."""
        return hashlib.md5(open(self._path, 'rb').read()).hexdigest()

    def as_zip_file(self) -> ZipFile:
        """Get the apk file as a zip file."""
        return ZipFile(self._path)

    def extract(self, path: str, members: Optional[Iterable[str]] = None) -> None:
        """
        Extract files from the apk to a directory.

        >>> apk_file.extract(path='out', members=['AndroidManifest.xml'])

        Args:
            path: Path to the directory to extract to.
            members: An optional list of names to extract. If not provided, all files will be extracted.
        """
        self.as_zip_file().extractall(path=path, members=members)

    def install(self, device_id: Optional[str] = None, adb_path: Optional[str] = None) -> None:
        """
        Install the apk to a device.

        Args:
            device_id: The device to install the apk to.
            adb_path: Path to adb binary (if not in PATH).
        """
        subprocess.run([adb_path or 'adb', *(('-s', device_id) if device_id else ()), 'install', self.path], check=True)

    def __repr__(self):
        return f"ApkFile(pkg='{self.package_name}', vcode={self.version_code} is_split={self.is_split})"

    def as_dict(self) -> Dict[str, Any]:
        return {k: v.as_dict() if hasattr(v, 'as_dict') else v
                for k, v in self.__dict__.items() if not k.startswith('_')}

