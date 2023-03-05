from setuptools import find_packages, setup
from apkfile import __version__

setup(
    name="apkfile",
    packages=find_packages(),
    version=__version__,
    description="Python wrapper for aapt • ApkFile, XapkFile, ApkmFile",
    long_description=(open('README.md', encoding='utf-8').read()),
    long_description_content_type="text/markdown",
    author_email='davidlev@telegmail.com',
    project_urls={
        "Documentation": "https://github.com/david-lev/apkfile#readme",
        "Issue Tracker": "https://github.com/david-lev/apkfile/issues",
        "Source Code": "https://github.com/david-lev/apkfile",
    },
    download_url="https://pypi.org/project/apkfile/",
    author='David Lev',
    license='MIT',
)
