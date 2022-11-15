import re
import subprocess
import shutil
from dataclasses import dataclass, asdict, fields, field
from enum import Enum
from typing import Optional, Dict, Union, Tuple


def get_aapt_path() -> str:
    aapt_path = shutil.which('aapt')
    if aapt_path is None:
        raise FileNotFoundError('aapt not found! see https://github.com/david-lev/aapyt#install-aapt')
    return aapt_path


def get_raw_aapt(apk_path: str, aapt_path: str = None) -> str:
    try:
        return subprocess.run(
            [aapt_path or get_aapt_path(), 'd', 'badging', apk_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=True).stdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        raise Exception(e.stderr.decode('utf-8'))


class InstallLocation(str, Enum):
    AUTO = 'auto'
    INTERNAL_ONLY = 'internalOnly'
    PREFER_EXTERNAL = 'preferExternal'

    @classmethod
    def _missing_(cls, value):
        return cls.AUTO

    def __repr__(self):
        return self.value


class Abi(str, Enum):
    ALL = 'all'
    ARM = 'armeabi'
    ARM7 = 'armeabi-v7a'
    ARM64 = 'arm64-v8a'
    X86 = 'x86'
    X86_64 = 'x86_64'

    @classmethod
    def _missing_(cls, value):
        return cls.ALL

    def __repr__(self):
        return self.value


@dataclass(frozen=True)
class ApkInfo:
    package_name: str = field(default=r'package: name=\'([^\']+)\'')
    version_code: int = field(default=r'versionCode=\'([^\']+)\'')
    version_name: Optional[str] = field(default=r'versionName=\'([^\']+)\'')
    min_sdk_version: Optional[int] = field(default=r'sdkVersion:\'([^\']+)\'')
    target_sdk_version: Optional[int] = field(default=r'targetSdkVersion:\'([^\']+)\'')
    install_location: Optional[InstallLocation] = field(default=r'install-location:\'([^\']+)\'')
    labels: Optional[Dict[str, str]] = field(default=r'application-label-([a-z]{2}):\'' + r'([^\']+)\'')
    permissions: Optional[Tuple[str]] = field(default=r'uses-permission: name=\'([^\']+)\'')
    libraries: Optional[Tuple[str]] = field(default=r'uses-library(?:-not-required)?:\'([^\']+)\'')
    features: Optional[Tuple[str]] = field(default=r'uses-feature(?:-not-required)?: name=\'([^\']+)\'')
    launchable_activity: Optional[str] = field(default=r'launchable-activity: name=\'([^\']+)\'')
    supported_screens: Optional[Tuple[str]] = field(default=r'supports-screens: \'([a-z\'\s]+)\'')
    supports_any_density: Optional[bool] = field(default=r'supports-any-density: \'([^\']+)\'')
    langs: Optional[Tuple[str]] = field(default=r'locales: \'([a-zA-Z\'\s\-\_]+)\'')
    densities: Optional[Tuple[str]] = field(default=r'densities: \'([0-9\'\s]+)\'')
    abis: Optional[Tuple[Abi]] = field(default=r'native-code: \'([^\']+)\'')
    icons: Optional[Dict[int, str]] = field(default=r'application-icon-([0-9]+):\'' + r'([^\']+)\'')
    split_name: Optional[str] = field(default=r'split=\'([^\']+)\'')
    is_split: bool = field(default=False)


def get_apk_info(apk_path: str, as_dict: bool = False, aapt_path: str = None) -> Union[ApkInfo, Dict]:
    raw = get_raw_aapt(apk_path, aapt_path)
    data = {f.name: re.findall(str(f.default), raw) for f in fields(ApkInfo)}
    info = ApkInfo(
        package_name=data['package_name'][0],
        version_code=int(data['version_code'][0]),
        version_name=data['version_name'][0] if data.get('version_name') else None,
        min_sdk_version=int(data['min_sdk_version'][0]) if data.get('min_sdk_version') else None,
        target_sdk_version=int(data['target_sdk_version'][0]) if data.get('target_sdk_version') else None,
        install_location=InstallLocation(data['install_location'][0]) if data.get(
            'install_location') else InstallLocation.AUTO,
        labels={lang: label for lang, label in data['labels']} if data.get('labels') else None,
        permissions=tuple(data['permissions']) if data.get('permissions') else None,
        libraries=tuple(data['libraries']) if data.get('libraries') else None,
        features=tuple(data['features']) if data.get('features') else None,
        launchable_activity=data['launchable_activity'][0] if data.get('launchable_activity') else None,
        supported_screens=tuple(re.split(r"'\s'", data['supports_screens'][0])) if data.get('supports_screens') else None,
        supports_any_density=(data['supports_any_density'][0] == 'true') if data.get(
            'supports_any_density') is not None else None,
        langs=tuple(lang.strip() for lang in re.split(r"'\s'", data['langs'][0]) if
                    re.match(r'^[A-Za-z\-]+$', lang)) if data.get('langs') else None,
        densities=tuple(re.split(r"'\s'", data['densities'][0])) if data.get('densities') else None,
        abis=tuple(Abi(abi) for abi in re.split(r"'\s'", data['abis'][0])) if data.get('abis') else Abi.ALL,
        icons={int(size): icon for size, icon in data['icons']} if data.get('icons') else None,
        split_name=data['split_name'][0] if data.get('split_name') else None,
        is_split=bool(data.get('split_name'))
    )

    return info if not as_dict else asdict(info)
