---
# ⛏️ AAPYT • Python wrapper for aapt
[![CodeFactor](https://www.codefactor.io/repository/github/david-lev/aapyt/badge)](https://www.codefactor.io/repository/github/david-lev/aapyt)

**AAPYT** is a Python wrapper for the Android Asset Packaging Tool ([aapt](https://elinux.org/Android_aapt)) that allows you to extract information from Android APK files.

*Why did I create aapyt?* There are several libraries that extract some data about APK files but not all the necessary data. Here you will of course receive `packageName`, ``versionCode`` and ``versionName``, but also data such as ``minSdk`` and ``targetSdk``, the ``labels`` of the application in different languages, ``permissions``, ``libraries`` and ``features``, ``supportedScreens`` and ``languages``, a path to the ``icons`` (which can be extracted with ``zipfile.ZipFile(apk_path).extract(icon_path)``, and of course, one of the more important data - which ``abis`` the application supports.

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
- If you do not have access to ``PATH``, you can manually provide a path to aapt by calling the ``get_apk_info(apk_path)`` function.

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
print(get_apk_info('/home/david/whatsapp.apk', as_dict=True))

# provide path to aapt
get_apk_info('/home/david/whatsapp.apk', aapt_path='./aapt')

# example to extract app icon
from zipfile import ZipFile
icon_480 = info.icons.get(480) if info.icons else None
if str(icon_480).endswith('.png'):
    ZipFile(apk_path).extract(icon_480)
```

The attributes ``install_location`` and ``abis`` come as values from Enum's in order to allow certainty for checking where the application can run.
You can import them from ``aapyt`` and check the values against them:
```python
from aapyt import InstallLocation, Abi
```
