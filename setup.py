#!/usr/bin/env python

from __future__ import unicode_literals
from __future__ import absolute_import
from setuptools import setup, find_packages
import re
import os
import codecs

def read(*parts):
    path = os.path.join(os.path.dirname(__file__), *parts)
    with codecs.open(path, encoding='utf-8') as fobj:
        return fobj.read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

with open('requirements.txt') as f:
    install_requires = f.read().splitlines()

setup(
    name='ferry',
    version=find_version("ferry", "__init__.py"),
    description=('Big data development environments using Docker'),
    url='http://ferry.opencore.io',
    author='OpenCore LLC',
    author_email='jlh@opencore.io',
    license='Apache License 2.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    scripts=['docker/docker-ferry'], 
    entry_points="""
    [console_scripts]
    ferry=ferry.cli.cli:main
    """
)
