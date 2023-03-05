# ⛏️ [apkfile](https://github.com/david-lev/apkfile) • Python wrapper for aapt
[![CodeFactor](https://www.codefactor.io/repository/github/david-lev/apkfile/badge)](https://www.codefactor.io/repository/github/david-lev/apkfile)
[![PyPI Downloads](https://img.shields.io/pypi/dm/apkfile?style=flat-square)](https://badge.fury.io/py/apkfile)
[![PyPI Version](https://badge.fury.io/py/apkfile.svg)](https://pypi.org/project/apkfile/)

**apkfile** is a Python wrapper for the Android Asset Packaging Tool ([aapt](https://elinux.org/Android_aapt)) that allows you to extract information from Android APK files.

*Why did I create apkfile?* There are several libraries for getting information from APK files, but most of them lack information such as `abis`, `min_sdk`, `split_name` and more. And besides, they are relatively complicated, there is nothing to get complicated here. Provide an apk file and receive the information.. simple and easy.

* Now `apkfile` supports `APK`, `XAPK`, and `APKM` files.

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
### Install aapt
apkfile requires ``aapt`` to be in the ``PATH``.
In each operating system, the way to install aapt is different, if you installed Android Studio, add one of the build-tools paths to the ``PATH``, if you are on a Debian-based Linux system (Ubuntu etc.) you can install with ``sudo apt install aapt``, and on Windows and Mac? Just google "How to install aapt on X".
- If you do not have access to ``PATH``, you can manually provide a path to aapt: ``ApkFile(..., aapt_path='/path/to/aapt')``.

## Usage

```python
from apkfile import ApkFile, XapkFile, ApkmFile

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

```
