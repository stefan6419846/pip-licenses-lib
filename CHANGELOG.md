# Development version

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
