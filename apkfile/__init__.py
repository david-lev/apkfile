from datetime import datetime
from apkfile.apk import ApkFile, Abi, InstallLocation, get_raw_aapt, install_apks
from apkfile.apkm import ApkmFile
from apkfile.xapk import XapkFile


__all__ = [
    'ApkFile',
    'ApkmFile',
    'XapkFile',
    'install_apks',
    'get_raw_aapt',
    'Abi',
    'InstallLocation'
]
__copyright__ = f'Copyright {datetime.now().year} david-lev'
__license__ = 'MIT'
__title__ = 'apkfile'
__version__ = '0.1.7'
