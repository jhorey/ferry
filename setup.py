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

def find_data_files(dir_path):
    all_files = {}
    for root, dirs, files in os.walk(dir_path):
        for f in files:
            if not root in all_files:
                all_files[root] = []
            all_files[root].append(root + os.sep + f)
    return all_files

def find_ferry_data_files():
    tuples = []

    tuples.extend(find_data_files('key').items())
    tuples.extend(find_data_files('plans').items())
    tuples.extend(find_data_files('templates').items())
    tuples.extend(find_data_files('conf').items())
    tuples.extend(find_data_files('dockerfiles').items())

    return tuples

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
    data_files=find_ferry_data_files(),
    entry_points="""
    [console_scripts]
    ferry=ferry.cli.cli:main
    """
)
