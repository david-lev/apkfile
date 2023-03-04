import json
import os
import tempfile
from typing import Optional, Union, Tuple
from aapyt._base_zip import _BaseZipApkFile


class XapkFile(_BaseZipApkFile):
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
    xapk_version: int
    app_name: str

    def __init__(
            self,
            path: Union[str, os.PathLike[str]],
            extract_path: Optional[Union[str, os.PathLike[str]]] = None,
            aapt_path: Optional[Union[str, os.PathLike[str]]] = None,
            skip_broken_splits: bool = False
    ):
        """
        Initialize an XapkFile instance.

        This will parse the xapk file and extract some basic information like package name, version code, etc.
        In default, the files in the xapk file will not be extracted. If you want to extract the files in order to
        get more information, you can set the `extract_path` argument to a directory path to extract the files to.

        If you try to access any of the non-basic information properties, the files will be extracted to a temporary
        directory and the properties will be parsed from the extracted files.


        Args:
            path: Path to the xapk file.
            extract_path: Path to extract the files in the xapk file to. If not provided, the files will not be extracted.
            skip_broken_splits: If True, broken split apks will be skipped. If False, an exception will be raised.
            aapt_path: Path to aapt binary (if not in PATH).

        Raises:
            FileNotFoundError: If aapt binary or xapk file not found.
            FileExistsError: If xapk file is not a valid xapk file (or when extracting files).
            RuntimeError: If aapt binary failed to run (When extracting files).
        """

        super().__init__(
            path=path,
            manifest_json_path='manifest.json',
            base_apk_path='{package_name}.apk',
            extract_path=extract_path,
            aapt_path=aapt_path,
            skip_broken_splits=skip_broken_splits
        )

        self.app_name = self._info['name']
        self.xapk_version = self._info['xapk_version']
        if not extract_path:
            self.package_name = self._info['package_name']
            self.version_code = int(self._info['version_code'])
            self.version_name = self._info.get('version_name')
            self.min_sdk_version = int(self._info['min_sdk_version'])
            self.target_sdk_version = int(self._info['target_sdk_version']) if 'target_sdk_version' in self._info else None
            self.permissions = self._info.get('permissions', ())
        else:
            self._extract()

    def __getattribute__(self, item):  # override target_sdk_version and permissions
        if item in ('base', 'splits', 'icon', 'features', 'libraries', 'labels', 'langs', 'supported_screens',
                    'launchable_activity', 'densities', 'supports_any_density'):
            self._extract()
        return super().__getattribute__(item)
