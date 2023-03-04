import os
from typing import Optional, Union
from apkfile._zip_apk import _BaseZipApkFile


class ApkmFile(_BaseZipApkFile):
    """
    An object representing an apkm file.

    From `fileinfo.com <https://fileinfo.com/extension/xapk>`_: An APKM file is an Android app bundle created for use with APKMirror Installer, an alternative Android app
    installer. It is similar to an .AAB file, in that it contains a number of .APK files used to install an Android
    app. APKM files, however, can be installed only using APKMirror Installer

        `APKMirror ↗️ <https://www.apkmirror.com/>`_

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
        apk_title: The title of the app (from APKMirror).
        apk_name: The name of the app (from APKMirror).
        apkm_version: The version of the apkm file.

    """
    apkm_version: int
    apk_name: str
    apk_title: str

    def __init__(
            self,
            path: Union[str, os.PathLike[str]],
            extract_path: Optional[Union[str, os.PathLike[str]]] = None,
            aapt_path: Optional[Union[str, os.PathLike[str]]] = None,
            skip_broken_splits: bool = False
    ):
        """
        Initialize an APKMFile instance.

        This will parse the apkm file and extract some basic information like package name, version code, etc.
        In default, the files in the apkm file will not be extracted. If you want to extract the files in order to
        get more information, you can set the `extract_path` argument to a directory path to extract the files to.

        If you try to access any of the non-basic information properties, the files will be extracted to a temporary
        directory and the properties will be parsed from the extracted files.


        Args:
            path: Path to the apkm file. (e.g. '/path/to/app.apkm')
            extract_path: Path to extract the files in the apkm file to. If not provided, the files will not be extracted.
            skip_broken_splits: If True, broken split apks will be skipped. If False, an exception will be raised.
            aapt_path: Path to aapt binary (if not in PATH).

        Raises:
            FileNotFoundError: If aapt binary or apkm file not found.
            FileExistsError: If apkm file is not a valid apkm file (or when extracting files).
            RuntimeError: If aapt binary failed to run (When extracting files).
        """
        super().__init__(
            path=path,
            manifest_json_path='info.json',
            base_apk_path='base.apk',
            extract_path=extract_path,
            aapt_path=aapt_path,
            skip_broken_splits=skip_broken_splits
        )

        self.apk_title = self._info['apk_title']
        self.app_name = self._info['app_name']
        self.apkm_version = self._info['apkm_version']
        if not extract_path:
            self.package_name = self._info['pname']
            self.version_code = self._info['versioncode']
            self.version_name = self._info['release_version']
            self.min_sdk_version = self._info['min_api']

        if extract_path:
            self._extract()

    def __repr__(self):
        return f"ApkmFile(pkg='{self.package_name}', vcode={self.version_code})"
