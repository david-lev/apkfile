import json
import os
import shutil
import tempfile
from typing import Tuple, Optional, Union
from zipfile import ZipFile
from apkfile.apk import _BaseApkFile, ApkFile, install_apks


class _BaseZipApkFile(_BaseApkFile):

    base: ApkFile
    splits: Tuple[ApkFile]
    icon: str

    def __init__(
            self,
            path: Union[str, os.PathLike[str]],
            manifest_json_path: str,
            base_apk_path: str,
            extract_path: Optional[Union[str, os.PathLike[str]]] = None,
            aapt_path: Optional[Union[str, os.PathLike[str]]] = None,
            skip_broken_splits: bool = False
    ):
        if isinstance(path, os.PathLike):
            path = os.fspath(path)
        self.path = path
        self.abis = tuple()  # every split has its own abi
        self._zipfile = ZipFile(self.path)
        try:
            with self._zipfile.open(manifest_json_path) as f:
                self._info = json.load(f)
                self._base_path = base_apk_path.format(**self._info)
        except (KeyError, json.JSONDecodeError) as e:
            raise FileExistsError(f'Invalid file: {self.path}') from e

        self._extract_path = extract_path or tempfile.mkdtemp()
        self._extracted = False
        self._splits_paths = list(filter(lambda x: x.endswith('.apk') and x != self._base_path, self._zipfile.namelist()))
        self._icon_path = 'icon.png'
        self._aapt_path = aapt_path
        self._skip_broken_splits = skip_broken_splits

    def __enter__(self):
        """Extract the apkm file to a directory."""
        self._extract()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Delete the extracted files."""
        self.delete_extracted_files()

    def _extract(self) -> None:
        """Extract the apkm file to a directory."""
        if self._extracted:
            return
        self._zipfile.extractall(path=self._extract_path, members=(self._base_path, *self._splits_paths, self._icon_path))
        self._extracted = True
        self.base = ApkFile(path=os.path.join(self._extract_path, self._base_path), aapt_path=self._aapt_path)
        self.icon = os.path.join(self._extract_path, self._icon_path)

        splits = []
        for split in self._splits_paths:
            try:
                splits.append(ApkFile(path=os.path.join(self._extract_path, split), aapt_path=self._aapt_path))
            except FileExistsError:
                if not self._skip_broken_splits:
                    raise
                os.unlink(os.path.join(self._extract_path, split))

        self.splits = tuple(splits)
        self.package_name = self.base.package_name
        self.version_code = self.base.version_code
        self.version_name = self.base.version_name
        self.min_sdk_version = self.base.min_sdk_version
        self.target_sdk_version = self.base.target_sdk_version
        self.permissions = tuple(set(p for split in self.splits for p in split.permissions) | set(self.base.permissions))
        self.features = tuple(set(f for split in self.splits for f in split.features) | set(self.base.features))
        self.libraries = tuple(set(l for split in self.splits for l in split.libraries) | set(self.base.libraries))
        self.labels = {k: v for labels in [split.labels for split in self.splits]
                       + [self.base.labels] for k, v in labels.items()}
        self.langs = tuple(set(lang for split in self.splits for lang in split.langs) | set(self.base.langs))
        self.supported_screens = self.base.supported_screens
        self.launchable_activity = self.base.launchable_activity
        self.densities = self.base.densities
        self.supports_any_density = self.base.supports_any_density

    def __getattribute__(self, item):
        """Extract the apkm file to a directory if needed."""
        if item in ('base', 'splits', 'icon', 'target_sdk_version',
                    'permissions', 'features', 'libraries', 'labels', 'langs', 'supported_screens',
                    'launchable_activity', 'densities', 'supports_any_density'):
            self._extract()
        return super().__getattribute__(item)

    def delete_extracted_files(self) -> None:
        """
        Delete the extracted files, Use this if you don't need the extracted files anymore.
            - This will not delete the apkm file, only the extracted files
            - The data will be remained in the object
        """
        if not self._extracted:
            return
        shutil.rmtree(self._extract_path)

    def install(
            self,
            delete_after_install: bool = False,
            check: bool = True,
            upgrade: bool = False,
            device_id: Optional[str] = None,
            installer: Optional[str] = None,
            originating_uri: Optional[str] = None,
            adb_path: Optional[str] = None,
            aapt_path: Optional[str] = None
    ):
        self._extract()
        install_apks(
            apks=(self.base.path, *(split.path for split in self.splits)),
            upgrade=upgrade,
            device_id=device_id,
            installer=installer,
            originating_uri=originating_uri,
            adb_path=adb_path
        )
        if delete_after_install:
            self.delete_extracted_files()
