# ⛏️ [AAPYT](https://github.com/david-lev/aapyt) • Python wrapper for aapt
[![CodeFactor](https://www.codefactor.io/repository/github/david-lev/aapyt/badge)](https://www.codefactor.io/repository/github/david-lev/aapyt)
[![PyPI Downloads](https://img.shields.io/pypi/dm/aapyt?style=flat-square)](https://badge.fury.io/py/aapyt)
[![PyPI Version](https://badge.fury.io/py/aapyt.svg)](https://pypi.org/project/aapyt/)

**AAPYT** is a Python wrapper for the Android Asset Packaging Tool ([aapt](https://elinux.org/Android_aapt)) that allows you to extract information from Android APK files.

*Why did I create aapyt?* There are several libraries for getting information from APK files, but most of them lack information such as `abis`, `min_sdk`, `split_name` and more. And besides, they are relatively complicated, there is nothing to get complicated here. Provide an apk file and receive the information.. simple and easy. See [Available attributes](#available-attributes).

## Usage

```python
from aapyt import get_apk_info

# get apk info
apk_path = '/home/david/whatsapp.apk'
info = get_apk_info(apk_path)
print(info.package_name) # com.whatsapp
print(info.version_code) # 222378000
print(info.labels.get('en') if info.labels else None) # WhatsApp
print(info.abis) # ['armeabi-v7a', 'arm64-v8a']

# get data as dict
print(get_apk_info(apk_path, as_dict=True))

# provide path to aapt
get_apk_info(apk_path, aapt_path='./aapt')

# example to extract app icon
from zipfile import ZipFile
icon_480 = info.icons.get(480) if info.icons else None
if str(icon_480).endswith('.png'):
    ZipFile(apk_path).extract(icon_480)
```

## Installation
### Install with pip
```bash
pip3 install -U aapyt
```
### Or, install from source:
```bash
git clone https://github.com/david-lev/aapyt.git
cd aapyt
python3 setup.py install
```
### Install aapt
aapyt requires ``aapt`` to be in the ``PATH``.
In each operating system, the way to install aapt is different, if you installed Android Studio, add one of the build-tools paths to the ``PATH``, if you are on a Debian-based Linux system (Ubuntu etc.) you can install with ``sudo apt install aapt``, and on Windows and Mac? Just google "How to install aapt on X".
- If you do not have access to ``PATH``, you can manually provide a path to aapt by calling the ``get_apk_info(..., aapt_path=PATH)`` function.

## Available attributes

- [``package_name``](https://support.google.com/admob/answer/9972781) • The package name of an Android app uniquely identifies the app on the device, in Google Play Store, and in supported third-party Android stores.
- [``version_code``](https://developer.android.com/studio/publish/versioning#appversioning) • The version code is an incremental integer value that represents the version of the application code.
- [``version_name``](https://developer.android.com/studio/publish/versioning#appversioning) • A string value that represents the release version of the application code.
- [``min_sdk_version``](https://developer.android.com/studio/publish/versioning#minsdkversion) • The minimum version of the Android platform on which the app will run.
- [``target_sdk_version``](https://developer.android.com/studio/publish/versioning#minsdkversion) • The API level on which the app is designed to run.
- [``install_location``](https://developer.android.com/guide/topics/data/install-location) • Where the application can be installed on external storage, internal only or auto.
- [``labels``](https://developer.android.com/guide/topics/manifest/application-element#:~:text=or%20getLargeMemoryClass().-,android%3Alabel,-A%20user%2Dreadable) • A user-readable labels for the application.
- [``permissions``](https://developer.android.com/guide/topics/manifest/uses-permission-element) • A system permission that the user must grant in order for the app to operate correctly.
- [``libraries``](https://developer.android.com/guide/topics/manifest/uses-library-element) • A shared libraries that the application must be linked against.
- [``features``](https://developer.android.com/guide/topics/manifest/uses-feature-element) • A hardware or software feature that is used by the application.
- [``supported_screens``](https://developer.android.com/guide/topics/manifest/supports-screens-element) • Screen sizes the application supports.
- [``launchable_activity``](https://developer.android.com/reference/android/app/Activity) • The main activity that can be launched.
- [``supports_any_density``](https://developer.android.com/guide/topics/manifest/supports-screens-element#any:~:text=API%20level%209.-,android%3AanyDensity,-Indicates%20whether%20the) • Indicates whether the application includes resources to accommodate any screen density.
- [``langs``](https://developer.android.com/guide/topics/resources/localization) • Supported languages.
- [``densities``](https://developer.android.com/guide/topics/large-screens/support-different-screen-sizes) • Supported pixel densities.
- [``abis``](https://developer.android.com/ndk/guides/abis) • Android supported ABIs.
- [``icons``](https://developer.android.com/guide/topics/resources/providing-resources) • Path's to the app icons.
- [``split_name``](https://developer.android.com/studio/build/configure-apk-splits.html) • The name of the split apk (if `is_split`).
- [``is_split``](https://developer.android.com/studio/build/configure-apk-splits.html) • True if the apk is split

---
The attributes ``install_location`` and ``abis`` come as values from Enum's in order to allow certainty for checking where the application can run.
You can import them from ``aapyt`` and check the values against them:
```python
from aapyt import InstallLocation, Abi
```
