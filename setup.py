from setuptools import find_packages, setup
from aapyt import __version__

setup(
    name="aapyt",
    packages=find_packages(),
    version=__version__,
    description="Python wrapper for aapt",
    long_description=(open('README.md', encoding='utf-8').read()),
    long_description_content_type="text/markdown",
    author_email='davidlev@telegmail.com',
    project_urls={
        "Documentation": "https://github.com/david-lev/aapyt#readme",
        "Issue Tracker": "https://github.com/david-lev/aapyt/issues",
        "Source Code": "https://github.com/david-lev/aapyt",
    },
    download_url="https://pypi.org/project/aapyt/",
    author='David Lev',
    license='MIT',
)
