from datetime import datetime
from aapyt.apk import ApkFile
from aapyt.apkm import ApkmFile
from aapyt.xapk import XapkFile
from aapyt.utils import Abi, InstallLocation, get_raw_aapt, install_apks


__all__ = [
    'ApkFile',
    'ApkmFile',
    'XapkFile',
    'Abi',
    'InstallLocation',
    'get_raw_aapt',
    '__copyright__',
    '__license__',
    '__title__',
    '__version__'
]
__copyright__ = f'Copyright {datetime.now().year} david-lev'
__license__ = 'MIT'
__title__ = 'aapyt'
__version__ = '0.1.7'
