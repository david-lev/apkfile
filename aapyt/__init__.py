from datetime import datetime
from aapyt.apk import ApkFile
from aapyt.apkm import APKMFile
from aapyt.xapk import XAPKFile
from aapyt.utils import Abi, InstallLocation, get_raw_aapt


__all__ = [
    'ApkFile',
    'APKMFile',
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
