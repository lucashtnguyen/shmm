#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

with open('README.md') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

PACKAGE_DATA = {
    'shmm.tests.baseline_images.test_viz': ['*png'],
    'shmm.tests.data': ['*'],
}

requirements = [
    # TODO: put package requirements here
    'geopandas',
    'hymo'
]

test_requirements = [
    # TODO: put package test requirements here
]

setup(
    name='shmm',
    version='0.0.1',
    description="SHMM converts shapefiles to a SWMM .inp ",
    long_description=readme + '\n\n' + history,
    author="Lucas Nguyen",
    author_email='lnguyen@geosyntec.com',
    url='https://github.com/lucashtnguyen/shmm',
    packages=[
        'shmm',
    ],
    package_dir={'shmm':
                 'shmm'},
    package_data=PACKAGE_DATA,
    include_package_data=True,
    install_requires=requirements,
    license="BSD license",
    zip_safe=False,
    keywords='shmm',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
