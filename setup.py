# Copyright (c) stefan6419846. All rights reserved.
# SPDX-License-Identifier: MIT
# See https://opensource.org/license/mit/ for the license text.

from pathlib import Path

import setuptools


ROOT_DIRECTORY = Path(__file__).parent.resolve()


setuptools.setup(
    name='pip-licenses-lib',
    description='Retrieve the software license list of Python packages installed with pip.',
    version='0.1.1',
    license='MIT',
    long_description=Path(ROOT_DIRECTORY / 'README.md').read_text(encoding='UTF-8'),
    long_description_content_type='text/markdown',
    author='stefan6419846',
    url='https://github.com/stefan6419846/pip-licenses-lib',
    packages=setuptools.find_packages(),
    include_package_data=True,
    python_requires=">=3.6, <4",
    install_requires=[
        'importlib_metadata; python_version < "3.8"',
    ],
    extras_require={
        'dev': [
            # Linting
            'flake8',
            'flake8-bugbear',
            'pep8-naming',
            'mypy',
            'types-requests',
            # Test code
            'requests',
            'pypdf',
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development',
        'Topic :: Utilities',
        'Typing :: Typed',
    ],
    keywords=['open source', 'license', 'package', 'dependency', 'licensing'],
)
