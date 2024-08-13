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

# TODO: Enable and change type hints accordingly after dropping support for Python < 3.8.
# from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field as dataclass_field
from email.message import Message
from enum import Enum, auto
try:
    from importlib import metadata as importlib_metadata
    from importlib.metadata import Distribution
except ImportError:
    # Python < 3.8
    import importlib_metadata  # type: ignore[import-not-found,no-redef,unused-ignore]
    from importlib_metadata import Distribution  # type: ignore[no-redef,assignment,unused-ignore]
from pathlib import Path
from typing import Callable, Dict, Generator, Iterator, List, Optional, Set, Tuple, Union


__pkgname__ = "pip-licenses-lib"
__version__ = "0.4.0"
__author__ = "raimon, stefan6419846"
__license__ = "MIT"
__summary__ = (
    "Retrieve the software license list of Python packages installed with pip."
)
__url__ = "https://github.com/stefan6419846/pip-licenses-lib"


def extract_homepage(metadata: Message) -> Optional[str]:
    """
    Extracts the homepage attribute from the package metadata.

    Not all Python packages have defined a home-page attribute.
    As a fallback, the `Project-URL` metadata can be used.
    The python core metadata supports multiple (free text) values for
    the `Project-URL` field that are comma separated.

    :param metadata: The package metadata to extract the homepage from.
    :return: The home page if applicable, None otherwise.
    """
    homepage: Optional[str] = metadata.get("home-page", None)
    if homepage is not None:
        return homepage

    candidates: Dict[str, str] = {}

    for entry in metadata.get_all("Project-URL", []):
        key, value = entry.split(",", 1)
        candidates[key.strip().lower()] = value.strip()

    for priority_key in [
            "homepage",
            "source",
            "repository",
            "changelog",
            "bug tracker",
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
METADATA_KEYS: Dict[str, List[Callable[[Message], Optional[str]]]] = {
    "homepage": [extract_homepage],
    "author": [
        lambda metadata: metadata.get("author"),
        lambda metadata: metadata.get("author-email"),
    ],
    "maintainer": [
        lambda metadata: metadata.get("maintainer"),
        lambda metadata: metadata.get("maintainer-email"),
    ],
    "license": [lambda metadata: metadata.get("license")],
    "summary": [lambda metadata: metadata.get("summary")],
}

LICENSE_UNKNOWN = "UNKNOWN"
"""
Identifier for unknown license data.
"""


def read_file(
        path: Union[str, Path]
) -> str:
    """
    Read the given file.

    :param path: Path to read from.
    :return: The file content as string.
    """
    return Path(path).read_text(encoding="utf-8", errors="backslashreplace")


def get_package_included_files(
        package: Distribution, file_names_regex: str
) -> Generator[Tuple[str, str], None, None]:
    """
    Attempt to find the package's included files on disk and return the
    tuple (included_file_path, included_file_contents).

    :param package: The package to work on.
    :param file_names_regex: The file name patterns to search for.
    :return: A list/generator of tuples holding the file path and the
             corresponding file content.
    """
    package_files = package.files or ()
    pattern = re.compile(file_names_regex)
    matched_relative_paths = filter(
        lambda entry: pattern.match(entry.name), package_files
    )
    for relative_path in matched_relative_paths:
        absolute_path = Path(package.locate_file(relative_path))  # type: ignore[arg-type,unused-ignore]  # TODO: Unused only required for Python <= 3.9.
        if not absolute_path.is_file():
            continue
        included_file = str(absolute_path)
        included_text = read_file(absolute_path)
        yield included_file, included_text


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

    licenses: List[Tuple[str, str]] = dataclass_field(default_factory=list)
    """
    List of license files and their contents.
    """

    license_classifiers: List[str] = dataclass_field(default_factory=list)
    """
    List of declared license classifiers.
    """

    license_names: Set[str] = dataclass_field(default_factory=set)
    """
    List of declared license names.
    """

    notices: List[Tuple[str, str]] = dataclass_field(default_factory=list)
    """
    List of notice files and their contents.
    """

    requirements: Set[str] = dataclass_field(default_factory=set)
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
    else:
        license_files = []
        notice_files = []

    name = package.metadata["name"]
    if normalize_name:
        name = normalize_package_name(name)
    package_info = PackageInfo(
        name=name,
        version=package.version,
        licenses=license_files,
        notices=notice_files,
        requirements=set(package.requires or []),
        distribution=package,
    )
    metadata = package.metadata
    for field_name, field_selector_functions in METADATA_KEYS.items():
        value = None
        for field_selector_function in field_selector_functions:
            # Type hint of `Distribution.metadata` states `PackageMetadata`
            # but it's actually of type `email.Message`
            value = field_selector_function(metadata)  # type: ignore[arg-type,unused-ignore]  # noqa: E501  # FIXME: Remove `unused-ignore` when dropping Python <= 3.9.
            if value:
                break
        setattr(package_info, field_name, value or LICENSE_UNKNOWN)

    classifiers: List[str] = metadata.get_all("classifier", [])
    package_info.license_classifiers = find_license_from_classifier(
        classifiers
    )

    return package_info


def get_python_sys_path(executable: Union[str, os.PathLike]) -> List[str]:  # type: ignore[type-arg]  # noqa: E501  # FIXME: Use `os.PathLike[str]` when dropping Python <= 3.7.
    """
    Get the value of `sys.path` for the given Python executable.

    :param executable: The Python executable to run for.
    :return: The corresponding `sys.path` entries.
    """
    script = "import sys; print(' '.join(filter(bool, sys.path)))"
    output: "subprocess.CompletedProcess[bytes]" = subprocess.run(  # type: ignore[call-overload]  # FIXME: Remove after dropping Python <= 3.7.
        [executable, "-c", script],
        **dict(capture_output=True) if sys.version_info >= (3, 7) else dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE),  # type: ignore[dict-item]  # noqa: E501
        env={**os.environ, "PYTHONPATH": "", "VIRTUAL_ENV": ""},
    )
    return output.stdout.decode().strip().split()


def get_packages(
        from_source: 'FromArg', python_path: Optional[Union[str, Path]] = None, include_files: bool = True,
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
    search_paths = sys.path if not python_path else get_python_sys_path(python_path)
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


def find_license_from_classifier(classifiers: List[str]) -> List[str]:
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
        from_source: 'FromArg', license_classifier: List[str], license_meta: str
) -> Set[str]:
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

    def __repr__(self) -> str:  # pragma: no cover
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
