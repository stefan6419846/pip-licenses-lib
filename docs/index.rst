Welcome to pip-licenses-lib's documentation!
============================================

Retrieve the software license list of Python packages installed with `pip`.

GitHub: `pip-license-lib <https://github.com/stefan6419846/pip-licenses-lib>`_

.. toctree::
   :maxdepth: 1

   api

About
-----

This package is a fork of the great `pip-licenses <https://github.com/raimon49/pip-licenses>`_ tool, which provides a CLI with similar functionality. For now, `pip-licenses` itself mostly focuses on the CLI part; while library-based access is possible, some interesting methods for further reuse are nested and therefore hidden inside the corresponding API.

While there have been some attempts to provide similar features in the upstream repository, they are not available inside the official package at the moment, while I needed a short-term solution. Examples:

* In May 2021, a package structure has been introduced by `#88 <https://github.com/raimon49/pip-licenses/pull/88>`_. In August 2023, this is still only available on a ``dev-4.0.0`` branch, while version 4.0.0 has been released in November 2022.
* In October 2020, the PR `#78 <https://github.com/raimon49/pip-licenses/pull/78>`_ for handling multiple license files has been closed to maybe include it in the future, which has not yet happened.

As parsing the license data of packages as provided by the maintainers is at least some first hint regarding the license status, I decided to create this fork with the required modifications and enhancements to suit my current needs.


Differences to pip-licenses
---------------------------

Changes compared to original version:

* Use ``dataclasses.dataclass`` instead of a dictionary for each package information result.
* Remove all output/rendering functionality.
* Move all methods to the top level.
* Always return all copyright and notice file matches.
* Always return the system packages as well.
* Include the license names and distribution object inside the result dictionary.
* Add option to skip retrieving license and notice files for faster version-only checks.
* Add option to normalize returned package names.
* Do not use abbreviations for naming purposes.
* Rewrite tests to use plain *unittest* functionality.

Installation
------------

You can install this package from PyPI:

.. code:: bash

    python -m pip install pip-licenses-lib

Alternatively, you can use the package from source directly after installing the required dependencies.


Usage
-----

The main entry point is ``piplicenses_lib.get_packages()``, which will yield a list of package data objects. For more details, see the :doc:`api` documentation itself.


License
-------

This package is subject to the terms of the MIT license.


Disclaimer
----------

All results are generated automatically from the data supplied by the corresponding package maintainers and provided on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. No generated content should be considered or used as legal advice. Consult an Attorney for any legal advice.


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
