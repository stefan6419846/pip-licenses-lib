# pip-licenses Library

Retrieve the software license list of Python packages installed with *pip*.

## About

This package is a fork of the great [pip-licenses](https://github.com/raimon49/pip-licenses) tool, which provides a CLI with similiar functionality. For now, *pip-licenses* itself mostly focuses on the CLI part; while library-based access is possible, some interesting methods for further reuse are nested and therefore hidden inside the corresponding API.

While there have been some attempts to provide similar features in the upstream repository, they are not available inside the official package at the moment, while I needed a short-term solution. Examples:

* In May 2021, a package structure has been introduced by [#88](https://github.com/raimon49/pip-licenses/pull/88). In August 2023, this is still only available on a `dev-4.0.0` branch, while version 4.0.0 has been released in November 2022.
* In October 2020, the PR [#78](https://github.com/raimon49/pip-licenses/pull/78) for handling multiple license files has been closed to maybe include it in the future, which has not yet happened.

As parsing the license data of packages as provided by the maintainers is at least some first hint regarding the license status, I decided to create this fork with the required modifications and enhancements to suit my current needs.

## Differences to pip-licenses

Changes compared to original version:

  * Enable support for Python < 3.8 by using the `importlib_metadata` backport and dropping support for the new annotations behaviour for now.
  * Remove all output/rendering functionality.
  * Move all methods to the top level.
  * Always return all copyright and notice file matches.
  * Always return the system packages as well.
  * Include the license names and distribution object inside the result dictionary.
  * Do not use abbreviations for naming purposes.
  * Rewrite tests to use plain *unittest* functionality.

## Installation

You can install this package from PyPI:

```bash
python -m pip install pip-licenses-lib
```

Alternatively, you can use the package from source directly after installing the required dependencies.

## Usage

The main entry point is `piplicenses_lib.get_packages()`, which will yield a list of package data dictionaries.

## License

This package is subject to the terms of the MIT license.

## Disclaimer

All results are generated automatically from the data supplied by the corresponding package maintainers and provided on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. No generated content should be considered or used as legal advice. Consult an Attorney for any legal advice.
