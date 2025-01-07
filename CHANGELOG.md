# Development version

# Version 0.5.0 - 2025-01-07

* Drop support for Python < 3.9.
* Add support for `License-Expression` field (PEP 639).

# Version 0.4.1 - 2024-08-14

* Fix detection of lowercase license and notice files.

# Version 0.4.0 - 2024-08-13

* Add option to normalize package names, defaulting to `True`.

# Version 0.3.0 - 2024-06-03

* Migrate from dictionary-based structure to `dataclasses.dataclass`.
  * Please note that this is a breaking change which should ease future maintainability.
  * Additionally, the corresponding attributes have been renamed to better match PEP8
    and make it clearer in some cases what these values actually refer to. 
* Migrate from `setup.py` to `pyproject.toml`.
* Add Read the Docs configuration.

# Version 0.2.1 - 2023-11-09

* Avoid bundling the tests within wheels.

# Version 0.2.0 - 2023-11-08

* Add option to skip retrieving license and notice files.

# Version 0.1.1 - 2023-08-21

* Fix type hints.
* Declare package as typed.

# Version 0.1.0 - 2023-08-03

* First public release.
