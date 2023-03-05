# ⛏️ [apkfile](https://github.com/david-lev/apkfile) • Python wrapper for aapt
[![CodeFactor](https://www.codefactor.io/repository/github/david-lev/apkfile/badge)](https://www.codefactor.io/repository/github/david-lev/apkfile)
[![PyPI Version](https://badge.fury.io/py/apkfile.svg)](https://pypi.org/project/apkfile/)

**apkfile** is a Python library that extracts information from ``.APK``, ``.APKM``, ``.XAPK``, and ``.APKS`` files using [``aapt``](https://elinux.org/Android_aapt). It provides additional metadata beyond what's available in the ``AndroidManifest.xml`` file, such as the abis, minSdkVersion, targetSdkVersion, and more.

## Installation
### Install with pip
```bash
pip3 install -U apkfile
```
### Or, install from source:
```bash
git clone https://github.com/david-lev/apkfile.git
cd apkfile
python3 setup.py install
```

You also need to install ``aapt`` (see [Install aapt](#install-aapt) below).

## Usage

```python
from apkfile import ApkFile, XapkFile, ApkmFile, ApksFile

# Get apk info
apk_file = ApkFile(path='/home/david/Downloads/wa.apk')
print(apk_file.package_name, apk_file.version_name, apk_file.version_code)
print(apk_file.as_dict())

# Get apkm info
apkm_file = ApkmFile('/home/david/Downloads/chrome.apkm')
for split in apkm_file.splits:
    print(split.split_name)
apkm_file.install(check=True, upgrade=True)

# Using context manager (delete the extracted files when done)
with XapkFile(path='/home/david/Downloads/telegram.xapk') as xf:
    print(xf.base.abis, x.permissions, x.langs)

# Get apks info
apks_file = ApksFile(path='/home/david/Downloads/facebook.apks')
print(apks_file.base.permissions, apks_file.md5, apks_file.sha256)

```

### Install aapt
apkfile requires ``aapt`` to be in the ``PATH``.
In each operating system, the way to install aapt is different, if you installed Android Studio, add one of the build-tools paths to the ``PATH``, if you are on a Debian-based Linux system (Ubuntu etc.) you can install with ``sudo apt install aapt``, and on Windows and Mac? Just google "How to install aapt on X".
- If you do not have access to ``PATH``, you can manually provide a path to aapt: ``ApkFile(..., aapt_path='/path/to/aapt')``.

