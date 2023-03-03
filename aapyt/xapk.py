import json
import os
import shutil
import tempfile
from typing import Tuple, Optional, Dict
from zipfile import ZipFile
from aapyt.apk import ApkFile
from aapyt.utils import Abi, InstallLocation, install_apks


class XapkFile:
    """
    An object representing a xapk file.

    From `fileinfo.com <https://fileinfo.com/extension/xapk>`_: An ``XAPK`` file is a package used to install Android apps on mobile devices. It is similar to the standard .APK format,
    but may contain other assets used by the app, such as an .OBB file, which stores graphics, media files, and other
    app data. XAPK files are used for distributing apps on third-party Android app download websites. They are not
    supported by Google Play.

        `APKPure ↗️ <https://apkpure.com/>`_

    Attributes:
        base: The base apk file.
        splits: A list of split apk files.
        icon: The icon of the app.
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

        xapk_version: The version of the xapk file.
        app_name: The name of the app (In APKPure, this is the name of the app in the xapk file).

    """
    base: ApkFile
    splits: Tuple[ApkFile]
    icon: str
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
    xapk_version: int
    app_name: str

    def __init__(
            self, xapk_path: str,
            extract_path: Optional[str] = None,
            skip_broken_splits: bool = True,
            aapt_path: Optional[str] = None
    ):
        """
        Initialize an APKMFile instance.

        This will parse the xapk file and extract some basic information like package name, version code, etc.
        In default, the files in the xapk file will not be extracted. If you want to extract the files in order to
        get more information, you can set the `extract_path` argument to a directory path to extract the files to.

        If you try to access any of the non-basic information properties, the files will be extracted to a temporary
        directory and the properties will be parsed from the extracted files.


        Args:
            xapk_path: Path to the xapk file.
            extract_path: Path to extract the files in the xapk file to. If not provided, the files will not be extracted.
            skip_broken_splits: If True, broken split apks will be skipped. If False, an exception will be raised.
            aapt_path: Path to aapt binary (if not in PATH).

        Raises:
            FileNotFoundError: If aapt binary or xapk file not found.
            FileExistsError: If xapk file is not a valid xapk file (or when extracting files).
            RuntimeError: If aapt binary failed to run (When extracting files).
        """
        self._path = xapk_path
        self._aapt_path = aapt_path
        self._skip_broken_splits = skip_broken_splits
        self._file = ZipFile(self._path)
        try:
            with self._file.open('manifest.json') as f:
                info = json.load(f)
        except (KeyError, json.JSONDecodeError):
            raise FileExistsError(f'Invalid xapk file: {self._path}')

        self.app_name = info['name']
        self.xapk_version = info['xapk_version']
        if not extract_path:
            self._package_name = info['package_name']
            self._version_code = info['version_code']
            self._version_name = info.get('version_name')
            self._min_sdk_version = info.get('min_sdk_version')
            self._target_sdk_version = info.get('target_sdk_version')
            self._permissions = info.get('permissions', ())

        self._extract_path = extract_path or tempfile.mkdtemp()
        self._extracted = False
        self._base = f'{self._package_name}.apk'
        self._splits = list(filter(lambda x: x.endswith('.apk') and x != self._base, self._file.namelist()))
        self._icon = 'icon.png'

        if extract_path:
            self._extract()

    def _extract(self) -> None:
        """Extract the xapk file to a directory."""
        if self._extracted:
            return
        self._file.extractall(path=self._extract_path, members=(self._base, *self._splits, self._icon))
        self._extracted = True
        self._base = ApkFile(apk_path=os.path.join(self._extract_path, self._base), aapt_path=self._aapt_path)
        splits = []
        for split in self._splits:
            try:
                splits.append(ApkFile(apk_path=os.path.join(self._extract_path, split), aapt_path=self._aapt_path))
            except RuntimeError:
                if not self._skip_broken_splits:
                    raise
                os.unlink(os.path.join(self._extract_path, split))

        self._package_name = self._base.package_name
        self._version_code = self._base.version_code
        self._version_name = self._base.version_name
        self._splits = tuple(splits)
        self._icon = os.path.join(self._extract_path, self._icon)
        self._supported_screens = self._base.supported_screens
        self._launchable_activity = self._base.launchable_activity
        self._densities = self._base.densities
        self._supports_any_density = self._base.supports_any_density

    def install(
            self,
            upgrade: bool = False,
            device_id: Optional[str] = None,
            installer: Optional[str] = None,
            originating_uri: Optional[str] = None,
            adb_path: Optional[str] = None
    ) -> None:
        """
        Install the xapk file.

        Args:
            upgrade: If True, the app will be upgraded if it is already installed.
            device_id: The device id to install the app to.
            installer: The installer package name.
            originating_uri: The originating uri.
            adb_path: Path to adb binary (if not in PATH).
        """
        self._extract()
        install_apks(
            apks=(self.base.path, *(split.path for split in self.splits)),
            upgrade=upgrade,
            device_id=device_id,
            installer=installer,
            originating_uri=originating_uri,
            adb_path=adb_path
        )

    def delete_extracted_files(self) -> None:
        """
        Delete the extracted files, Use this if you don't need the extracted files anymore.
            - This will not delete the xapk file, only the extracted files
            - The data will be remained in the object
        """
        if not self._extracted:
            return
        shutil.rmtree(self._extract_path)

    @property
    def base(self) -> ApkFile:
        """Get the base apk file."""
        self._extract()
        return self._base

    @property
    def splits(self) -> Tuple[ApkFile]:
        """Get the split apk files."""
        self._extract()
        return self._splits

    @property
    def package_name(self) -> str:
        """Get the package name."""
        return self._package_name

    @property
    def version_code(self) -> int:
        """Get the version code."""
        return self._version_code

    @property
    def version_name(self) -> str:
        """Get the version name."""
        return self._version_name

    @property
    def icon(self) -> str:
        """Get the icon file path."""
        self._extract()
        return self._icon

    @property
    def min_sdk_version(self) -> int:
        """Get the min sdk version."""
        return self._min_sdk_version

    @property
    def target_sdk_version(self) -> int:
        """Get the target sdk version."""
        return self._target_sdk_version

    @property
    def permissions(self) -> Tuple[str]:
        """Get the permissions."""
        self._extract()
        return tuple(set(p for split in self._splits for p in split.permissions) | set(self._base.permissions))

    @property
    def features(self) -> Tuple[str]:
        """Get the features."""
        self._extract()
        return tuple(set(f for split in self._splits for f in split.features) | set(self._base.features))

    @property
    def libraries(self) -> Tuple[str]:
        """Get the libraries."""
        self._extract()
        return tuple(set(l for split in self._splits for l in split.libraries) | set(self._base.libraries))

    @property
    def supported_screens(self) -> Tuple[str]:
        """Get the supported screens."""
        self._extract()
        return self._supported_screens

    @property
    def launchable_activity(self) -> str:
        """Get the launchable activity."""
        self._extract()
        return self._launchable_activity

    @property
    def labels(self) -> Dict[str, str]:
        """Get the labels."""
        self._extract()
        return {k: v for labels in [split.labels for split in self._splits]
                + [self._base.labels] for k, v in labels.items()}

    @property
    def densities(self) -> Tuple[str]:
        """Get the densities."""
        self._extract()
        return self._densities

    @property
    def supports_any_density(self) -> bool:
        """Get whether the app supports any density."""
        self._extract()
        return self._supports_any_density

    @property
    def langs(self) -> Tuple[str]:
        """Get the locals."""
        self._extract()
        return tuple(set(lang for split in self._splits for lang in split.langs) | set(self._base.langs))

    @property
    def abis(self) -> Tuple[Abi]:
        """Get the abis."""
        self._extract()
        return tuple(set(abi for split in self._splits for abi in split.abis) | set(self._base.abis))

    def __repr__(self):
        return f"XapkFile(pkg='{self.package_name}', vcode={self.version_code})"
