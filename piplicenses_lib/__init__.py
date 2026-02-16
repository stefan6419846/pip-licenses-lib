# pip-licenses-lib
#
# MIT License
#
# Copyright (c) 2018 raimon
# Copyright (c) 2023 stefan6419846
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import itertools
import json
import os
import re
import string
import subprocess
import sys
from dataclasses import dataclass, field as dataclass_field
from email.message import Message
from enum import Enum, auto
from importlib import metadata as importlib_metadata
from importlib.metadata import Distribution, PathDistribution
from operator import itemgetter
from pathlib import Path
from typing import Callable, cast, Generator, Iterable, Iterator

__pkgname__ = "pip-licenses-lib"
__version__ = "1.1.0"
__author__ = "raimon, stefan6419846"
__license__ = "MIT"
__summary__ = (
    "Retrieve the software license list of Python packages installed with pip."
)
__url__ = "https://github.com/stefan6419846/pip-licenses-lib"


def extract_homepage(metadata: Message) -> str | None:
    """
    Extracts the homepage attribute from the package metadata.

    Some packages might use the legacy direct `home-page` key, while
    most use the project URLs field. With its free-text behavior,
    multiple candidates are available to choose from.

    :param metadata: The package metadata to extract the homepage from.
    :return: The homepage if applicable, None otherwise.
    """
    candidates: dict[str, str] = {}
    value: str | None

    for entry in metadata.get_all("Project-URL", []):
        # https://packaging.python.org/en/latest/specifications/well-known-project-urls/#label-normalization
        chars_to_remove = string.punctuation + string.whitespace
        removal_map = str.maketrans("", "", chars_to_remove)
        key, value = entry.split(",", 1)
        label = key.translate(removal_map).lower()
        candidates[label] = value.strip()

    if value := candidates.get("homepage"):
        # Primary value.
        return value
    if value := metadata.get("home-page"):
        # Legacy value.
        return value

    # https://packaging.python.org/en/latest/specifications/well-known-project-urls/#well-known-labels
    for priority_key in [
            "source",
            "sourcecode",
            "repository",
            "github",
            "documentation",
            "docs",
            "bugtracker",
            "issues",
            "changelog",
            "changes",
            "whatsnew",
            "releasenotes",
    ]:
        if priority_key in candidates:
            return candidates[priority_key]

    return None


# Regex pattern for normalizing package names according to PEP 503.
PATTERN_PACKAGE_NAME_DELIMITER = re.compile(r"[-_.]+")


def normalize_package_name(package_name: str) -> str:
    """
    Return normalized name according to PEP specification

    See here: https://peps.python.org/pep-0503/#normalized-names

    :param package_name: Package name as it is extracted from the package metadata
                         or specified as parameter somewhere.
    :return: Normalized package name.
    """
    return PATTERN_PACKAGE_NAME_DELIMITER.sub("-", package_name).lower()


# Mapping of how to retrieve the different metadata fields.
METADATA_KEYS: dict[str, list[Callable[[Message], str | None]]] = {
    "homepage": [extract_homepage],
    "author": [
        lambda metadata: metadata.get("author"),
        lambda metadata: metadata.get("author-email"),
    ],
    "maintainer": [
        lambda metadata: metadata.get("maintainer"),
        lambda metadata: metadata.get("maintainer-email"),
    ],
    "license": [
        # From https://packaging.python.org/en/latest/specifications/core-metadata/#license:
        #
        # > As of Metadata 2.4, `License` and `License-Expression` are mutually exclusive. If both are specified,
        # > tools which parse metadata will disregard `License` and PyPI will reject uploads. See
        # > [PEP 639](https://peps.python.org/pep-0639/#deprecate-license-field).
        lambda metadata: metadata.get("license-expression"),
        lambda metadata: metadata.get("license"),
    ],
    "summary": [lambda metadata: metadata.get("summary")],
}

LICENSE_UNKNOWN = "UNKNOWN"
"""
Identifier for unknown license data.
"""


def read_file(
        path: str | Path
) -> str:
    """
    Read the given file.

    :param path: Path to read from.
    :return: The file content as string.
    """
    return Path(path).read_text(encoding="utf-8", errors="backslashreplace")


def get_package_included_files(
        package: Distribution, file_names_regex: str
) -> Generator[tuple[str, str]]:
    """
    Attempt to find the package's included files on disk and return the
    tuple (included_file_path, included_file_contents).

    :param package: The package to work on.
    :param file_names_regex: The file name patterns to search for.
    :return: A list/generator of tuples holding the file path and the
             corresponding file content.
    """
    package_files = package.files or ()
    pattern = re.compile(file_names_regex, flags=re.IGNORECASE)
    matched_relative_paths = filter(
        lambda entry: pattern.match(entry.name), package_files
    )
    for relative_path in matched_relative_paths:
        absolute_path = Path(package.locate_file(relative_path))  # type: ignore[arg-type]
        if not absolute_path.is_file():
            continue
        included_file = str(absolute_path)
        included_text = read_file(absolute_path)
        yield included_file, included_text


def _locate_license_file(package: Distribution, name: str) -> Path | None:
    """
    Resolve the given License-File value to an actual path according to PEP 639.

    References: https://peps.python.org/pep-0639/#license-files-in-project-formats

    :param package: The package to work on.
    :param name: The name of the license file to find.
    :return: The corresponding path for valid cases, `None` otherwise.
    """
    if not isinstance(package, PathDistribution):
        return None
    path = Path(str(package._path), "licenses", name)
    if path.is_file():
        # Built distributions and installed projects.
        return path
    # Do not care about source distributions, as these are never installed directly.
    return None


def _get_other_files(package: Distribution, existing_files: Iterable[tuple[str, str]]) -> Generator[tuple[str, str]]:
    """
    Get other License-File entries.

    :param package: The package to work on.
    :param existing_files: The files already covered by license and notice file matching.
    :return: A list/generator of tuples holding the file path and corresponding file content.
    """
    known_names = set(map(itemgetter(0), existing_files))
    for other_file in package.metadata.get_all("License-File") or []:
        other_file_resolved = _locate_license_file(package, other_file)
        other_file_str = str(other_file_resolved)
        if other_file_resolved is None or other_file_str in known_names:
            continue
        yield other_file_str, read_file(other_file_resolved)


def _get_sboms(package: Distribution) -> Generator[tuple[str, str]]:
    """
    Get PEP 770 compliant files.

    References:
        * https://peps.python.org/pep-0770/
        * https://packaging.python.org/en/latest/specifications/binary-distribution-format/#the-dist-info-sboms-directory

    :param package: The package to work on.
    :return: A list/generator of tuples holding the file path and corresponding file content.
    """
    if not isinstance(package, PathDistribution):
        return
    path = Path(str(package._path), "sboms")
    if not path.is_dir():
        # No SBOMs
        return
    for inner_path in sorted(path.iterdir()):
        yield str(inner_path), read_file(inner_path)


@dataclass
class PackageInfo:
    """
    Hold the information on one specific package.
    """

    name: str
    """
    The package name.
    """

    version: str
    """
    The package version.
    """

    distribution: Distribution
    """
    The corresponding distribution object.
    """

    homepage: str = LICENSE_UNKNOWN
    """
    The corresponding homepage.
    """

    author: str = LICENSE_UNKNOWN
    """
    The package author.
    """

    maintainer: str = LICENSE_UNKNOWN
    """
    The package maintainer.
    """

    license: str = LICENSE_UNKNOWN
    """
    The declared license.
    """

    summary: str = LICENSE_UNKNOWN
    """
    The package summary.
    """

    licenses: list[tuple[str, str]] = dataclass_field(default_factory=list)
    """
    List of license files and their contents.
    """

    license_classifiers: list[str] = dataclass_field(default_factory=list)
    """
    List of declared license classifiers.
    """

    license_names: set[str] = dataclass_field(default_factory=set)
    """
    List of declared license names.
    """

    notices: list[tuple[str, str]] = dataclass_field(default_factory=list)
    """
    List of notice files and their contents.
    """

    others: list[tuple[str, str]] = dataclass_field(default_factory=list)
    """
    List of other licensing-related files and their contents.
    """

    sboms: list[tuple[str, str]] = dataclass_field(default_factory=list)
    """
    List of SBOM files and their contents.
    """

    requirements: set[str] = dataclass_field(default_factory=set)
    """
    Collection of all declared (direct) requirements.
    """

    @property
    def name_version(self) -> str:
        """
        String consisting of package name and version.
        """
        return f"{self.name} {self.version}"

    @property
    def license_files(self) -> Iterator[str]:
        """
        List of license file paths.
        """
        for entry in self.licenses:
            yield entry[0]

    @property
    def license_texts(self) -> Iterator[str]:
        """
        List of license texts.
        """
        for entry in self.licenses:
            yield entry[1]

    @property
    def notice_files(self) -> Iterator[str]:
        """
        List of notice file paths.
        """
        for entry in self.notices:
            yield entry[0]

    @property
    def notice_texts(self) -> Iterator[str]:
        """
        List of notice texts.
        """
        for entry in self.notices:
            yield entry[1]

    @property
    def other_files(self) -> Iterator[str]:
        """
        List of other licensing-related file paths.
        """
        for entry in self.others:
            yield entry[0]

    @property
    def other_texts(self) -> Iterator[str]:
        """
        List of other licensing-related texts.
        """
        for entry in self.others:
            yield entry[1]

    @property
    def sbom_files(self) -> Iterator[str]:
        """
        List of SBOM file paths.
        """
        for entry in self.sboms:
            yield entry[0]

    @property
    def sbom_texts(self) -> Iterator[str]:
        """
        List of SBOM contents.
        """
        for entry in self.sboms:
            yield entry[1]


def get_package_info(
        package: Distribution, include_files: bool = True, normalize_name: bool = True,
) -> PackageInfo:
    """
    Retrieve the relevant information for the given package.

    :param package: The package to work on.
    :param include_files: Retrieve license, copying and notice files.
    :param normalize_name: Normalize the package name.
    :return: The retrieved metadata/package information.
    """
    if include_files:
        license_files = list(get_package_included_files(
            package, "LICEN[CS]E.*|COPYING.*"
        ))
        notice_files = list(get_package_included_files(package, "NOTICE.*"))
        other_files = list(_get_other_files(package, itertools.chain(license_files, notice_files)))
        sboms = list(_get_sboms(package))
    else:
        license_files = []
        notice_files = []
        other_files = []
        sboms = []

    name = package.metadata["name"]
    if normalize_name:
        name = normalize_package_name(name)
    package_info = PackageInfo(
        name=name,
        version=package.version,
        licenses=license_files,
        notices=notice_files,
        others=other_files,
        sboms=sboms,
        requirements=set(package.requires or []),
        distribution=package,
    )
    metadata = package.metadata
    for field_name, field_selector_functions in METADATA_KEYS.items():
        value = None
        for field_selector_function in field_selector_functions:
            # Type hint of `Distribution.metadata` states `PackageMetadata`
            # but it's actually of type `email.Message`
            value = field_selector_function(metadata)  # type: ignore[arg-type]
            if value:
                break
        setattr(package_info, field_name, value or LICENSE_UNKNOWN)

    classifiers: list[str] = metadata.get_all("classifier", [])
    package_info.license_classifiers = find_license_from_classifier(
        classifiers
    )

    return package_info


def get_python_sys_path(executable: os.PathLike[str] | str) -> list[str]:
    """
    Get the value of `sys.path` for the given Python executable.

    :param executable: The Python executable to run for.
    :return: The corresponding `sys.path` entries.
    """
    script = "import json, sys; print(json.dumps(list(filter(bool, sys.path))))"
    output: subprocess.CompletedProcess[bytes] = subprocess.run(
        [executable, "-c", script],
        capture_output=True,
        env={**os.environ, "PYTHONPATH": "", "VIRTUAL_ENV": ""},
    )
    return cast(list[str], json.loads(output.stdout))


def get_packages(
        from_source: FromArg,
        python_path: os.PathLike[str] | str | None = None,
        include_files: bool = True,
        normalize_names: bool = True,
) -> Iterator[PackageInfo]:
    """
    Get the packages for the given Python interpreter.

    This is the main entry point for querying.

    :param from_source: The source to use for metadata querying, for example
                        regarding the license.
    :param python_path: The Python executable to use. If unset, uses the
                        current interpreter.
    :param include_files: Retrieve license, copying and notice files.
    :param normalize_names: Normalize the package names.
    :return: The corresponding package information.
    """
    if python_path is not None:
        search_paths = get_python_sys_path(python_path)
    else:
        search_paths = sys.path
    # Remove duplicates keeping the order as intended.
    # Example: In some environments, `lib64` links to `lib`, thus generating duplicates
    # for the same path.
    search_paths = list(dict.fromkeys(str(Path(path).resolve()) for path in search_paths))

    packages = importlib_metadata.distributions(path=search_paths)

    for package in packages:
        package_info = get_package_info(package=package, include_files=include_files, normalize_name=normalize_names)

        license_names = select_license_by_source(
            from_source,
            package_info.license_classifiers,
            package_info.license,
        )
        package_info.license_names = license_names

        yield package_info


def find_license_from_classifier(classifiers: list[str]) -> list[str]:
    """
    Search inside the given classifiers for licenses.

    :param classifiers: The classifiers to search inside.
    :return: The OSI licenses found.
    """
    licenses = []
    for classifier in filter(lambda c: c.startswith("License"), classifiers):
        license_ = classifier.split(" :: ")[-1]

        # Through the declaration of 'Classifier: License :: OSI Approved'
        if license_ != "OSI Approved":
            licenses.append(license_)

    return licenses


def select_license_by_source(
        from_source: FromArg, license_classifier: list[str], license_meta: str
) -> set[str]:
    """
    Decide which license source to use.

    :param from_source: The source configuration.
    :param license_classifier: The list of licenses retrieved from the trove
                               classifiers.
    :param license_meta: The license data retrieved from the package metadata.
    :return: The selected licenses.
    """
    license_classifier_set = set(license_classifier) or {LICENSE_UNKNOWN}
    if (
            from_source == FromArg.CLASSIFIER
            or from_source == FromArg.MIXED
            and len(license_classifier) > 0
    ):
        return license_classifier_set
    else:
        return {license_meta}


class NoValueEnum(Enum):
    """
    Enumeration which has no usable/readable values defined.
    """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}.{self.name}>"


class FromArg(NoValueEnum):
    """
    Source specification.
    """

    META = auto()
    """
    Retrieve from metadata field only.
    """

    CLASSIFIER = auto()
    """
    Retrieve from classifiers only.
    """

    MIXED = auto()
    """
    Prefer classifiers over the metadata field.
    """

    ALL = auto()
    """
    Retrieve from all. Currently not implemented.
    """
