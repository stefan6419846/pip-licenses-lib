"""
pip-licenses-lib

MIT License

Copyright (c) 2018 raimon
Copyright (c) 2023 stefan6419846

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
# TODO: Enable and change type hints accordingly after dropping support for Python < 3.8.
# from __future__ import annotations

import shutil
import subprocess
import sys
from contextlib import contextmanager
from importlib.metadata import PathDistribution
from operator import attrgetter
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from types import SimpleNamespace
from typing import cast, Any, Generator, List, Optional, Union
from unittest import TestCase
from unittest.mock import MagicMock
from venv import EnvBuilder as _EnvBuilder


import requests
from piplicenses_lib import (  # type: ignore[attr-defined]
    Distribution,
    extract_homepage,
    find_license_from_classifier,
    FromArg,
    get_packages,
    get_package_included_files,
    get_package_info,
    LICENSE_UNKNOWN,
    normalize_package_name,
    PackageInfo,
    read_file,
    select_license_by_source
)
from requests.utils import CaseInsensitiveDict


class EnvBuilder(_EnvBuilder):
    context = None
    executable: str = ""

    def post_setup(self, context: SimpleNamespace) -> None:
        self.context = context
        self.executable = self.context.env_exe


@contextmanager
def create_temporary_venv(additional_packages: Optional[List[str]] = None) -> Generator[EnvBuilder, None, None]:
    with TemporaryDirectory() as environment_path:
        venv_builder = EnvBuilder(with_pip=True)
        venv_builder.create(environment_path)

        if additional_packages:
            for additional_package in additional_packages:
                subprocess.check_output([venv_builder.executable, "-m", "pip", "install", additional_package])
        yield venv_builder


class ExtractHomepageTestCase(TestCase):
    def test_extract_homepage__home_page_set(self) -> None:
        metadata = MagicMock()
        metadata.get.return_value = "Foobar"
        self.assertEqual("Foobar", extract_homepage(metadata=metadata))

        metadata.get.assert_called_once_with("home-page", None)

    def test_extract_homepage__project_url_fallback(self) -> None:
        metadata = MagicMock()
        metadata.get.return_value = None

        # `Homepage` is prioritized higher than `Source`
        metadata.get_all.return_value = [
            "Source, source",
            "Homepage, homepage",
        ]

        self.assertEqual("homepage", extract_homepage(metadata=metadata))

        metadata.get_all.assert_called_once_with("Project-URL", [])

    def test_extract_homepage__project_url_fallback__multiple_parts(self) -> None:
        metadata = MagicMock()
        metadata.get.return_value = None

        # `Homepage` is prioritized higher than `Source`
        metadata.get_all.return_value = [
            "Source, source",
            "Homepage, homepage, foo, bar",
        ]

        self.assertEqual("homepage, foo, bar", extract_homepage(metadata=metadata))

        metadata.get_all.assert_called_once_with("Project-URL", [])

    def test_extract_homepage__empty(self) -> None:
        metadata = MagicMock()

        metadata.get.return_value = None
        metadata.get_all.return_value = []

        self.assertIsNone(extract_homepage(metadata=metadata))

        metadata.get.assert_called_once_with("home-page", None)
        metadata.get_all.assert_called_once_with("Project-URL", [])

    def test_extract_homepage__project_url_fallback__capitalisation(self) -> None:
        metadata = MagicMock()
        metadata.get.return_value = None

        # `homepage` is still prioritized higher than `Source` (capitalisation)
        metadata.get_all.return_value = [
            "Source, source",
            "homepage, homepage",
        ]

        self.assertEqual("homepage", extract_homepage(metadata=metadata))

        metadata.get_all.assert_called_once_with("Project-URL", [])


class NormalizePackageNameTestCase(TestCase):
    def test_normalize_package_name(self) -> None:
        expected_normalized_name = "pip-licenses"

        for name in ["pip_licenses", "pip.licenses", "Pip-Licenses"]:
            with self.subTest(name=name):
                self.assertEqual(expected_normalized_name, normalize_package_name(name))


class ReadFileTestCase(TestCase):
    def test_read_file__regular(self) -> None:
        with NamedTemporaryFile(mode="w+t") as fd:
            fd.write("Test text\nabc\n")
            fd.seek(0)
            for path in [fd.name, Path(fd.name)]:
                path = cast(Union[str, Path], path)
                with self.subTest(path=path):
                    self.assertEqual("Test text\nabc\n", read_file(path))

    def test_read_file__replace(self) -> None:
        with NamedTemporaryFile(mode="w+b") as fd:
            fd.write(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x42abc123")
            fd.seek(0)
            self.assertEqual("\x00\x01\x02\x03\x04\x05\x06\x07\x08\tBabc123", read_file(fd.name))


class GetPackageIncludedFilesTestCase(TestCase):
    pypdf: Distribution = None  # type: ignore[assignment]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.pypdf = Distribution.from_name("pypdf")

    def test_get_package_included_files__no_match(self) -> None:
        results = list(get_package_included_files(package=self.pypdf, file_names_regex="MY_INVALID_FILE*"))
        self.assertListEqual([], results)

    def test_get_package_included_file__one_match(self) -> None:
        results = list(get_package_included_files(package=self.pypdf, file_names_regex=r"pagerange\.py"))
        self.assertEqual(1, len(results), results)
        self.assertEqual(str(self.pypdf.locate_file("pypdf/pagerange.py")), results[0][0])
        self.assertIn("Representation and utils for ranges of PDF file pages.\n", results[0][1])

    def test_get_package_included_file__multiple_matches(self) -> None:
        results = list(get_package_included_files(package=self.pypdf, file_names_regex=r"_.*\.py"))
        self.assertLessEqual(1, len(results), results)
        paths = {result[0] for result in results}
        self.assertIn(
            str(self.pypdf.locate_file("pypdf/_encryption.py")),
            paths
        )

    def test_get_package_included_file__casing(self) -> None:
        results = list(get_package_included_files(package=self.pypdf, file_names_regex=r"_.*\.PY"))
        self.assertLessEqual(1, len(results), results)
        paths = {result[0] for result in results}
        self.assertIn(
            str(self.pypdf.locate_file("pypdf/_encryption.py")),
            paths
        )


class DummyDistribution:
    class MyDict(CaseInsensitiveDict):  # type: ignore[type-arg]  # noqa: E501  # FIXME: Use `CaseInsensitiveDict[Any]` when dropping Python <= 3.8.
        def get_all(self, key: str, default: Optional[Any] = None) -> List[Any]:
            value = self.get(key, default=default)
            if not isinstance(value, list):
                raise ValueError("get_all called for non-list value")
            return value

    def __init__(self, name: str = "dummy", version: str = "42"):
        self.metadata = self.MyDict(name=name)
        self.files: List[Any] = []
        self.version = version
        self.requires: List[str] = []


class PackageInfoTestCase(TestCase):
    def test_name_version(self) -> None:
        package = PackageInfo(name="my-package", version="1.2.4-rc1", distribution=DummyDistribution())  # type: ignore[arg-type]
        self.assertEqual(
            "my-package 1.2.4-rc1",
            package.name_version
        )

    def test_licenses(self) -> None:
        package = PackageInfo(name="my-package", version="1.2.4-rc1", distribution=DummyDistribution())  # type: ignore[arg-type]
        package.licenses = [
            ("/path/to/license1", "First license text"),
            ("/path/to/another/license", "This is my text.")
        ]
        self.assertEqual(
            ["/path/to/license1", "/path/to/another/license"],
            list(package.license_files)
        )
        self.assertEqual(
            ["First license text", "This is my text."],
            list(package.license_texts)
        )

    def test_notices(self) -> None:
        package = PackageInfo(name="my-package", version="1.2.4-rc1", distribution=DummyDistribution())  # type: ignore[arg-type]
        package.notices = [
            ("/path/to/some/notice", "Some notice text."),
            ("/path/to/NOTICE.md", "Hello World!")
        ]
        self.assertEqual(
            ["/path/to/some/notice", "/path/to/NOTICE.md"],
            list(package.notice_files)
        )
        self.assertEqual(
            ["Some notice text.", "Hello World!"],
            list(package.notice_texts)
        )


class GetPackageInfoTestCase(TestCase):
    def assertStartsWith(self, expected: str, actual: str, message: Optional[str] = None) -> None:  # noqa: N802
        self.assertEqual(expected, actual[:len(expected)], message)

    def assertEndsWith(self, expected: str, actual: str, message: Optional[str] = None) -> None:  # noqa: N802
        self.assertEqual(expected, actual[-len(expected):], message)

    def test_get_package_info(self) -> None:
        import pypdf
        version = pypdf.__version__

        distribution = Distribution.from_name("pypdf")

        for include_files in [True, False]:
            with self.subTest(include_files=include_files):
                package_info = get_package_info(distribution, include_files=include_files)
                self.assertEqual("pypdf", package_info.name)
                self.assertEqual(version, package_info.version)
                self.assertEqual(f"pypdf {version}", package_info.name_version)
                license_files = list(package_info.license_files)
                license_texts = list(package_info.license_texts)
                if include_files:
                    self.assertEqual(1, len(license_files), license_files)
                    self.assertEndsWith(".dist-info/LICENSE", license_files[0])
                    self.assertEqual(1, len(license_texts), license_texts)
                    self.assertStartsWith("Copyright (c) 2006-2008, Mathieu Fenniak\nSome contributions copyright (c) 2007, Ashish", license_texts[0])
                    self.assertEndsWith(", EVEN IF ADVISED OF THE\nPOSSIBILITY OF SUCH DAMAGE.\n", license_texts[0])
                else:
                    self.assertEqual([], license_files)
                    self.assertEqual([], license_texts)
                self.assertEqual(0, len(list(package_info.notice_files)), list(package_info.notice_files))
                self.assertEqual(0, len(list(package_info.notice_texts)), list(package_info.notice_texts))
                self.assertIs(distribution, package_info.distribution)
                self.assertEqual("https://github.com/py-pdf/pypdf", package_info.homepage)
                self.assertEqual("Mathieu Fenniak <biziqe@mathieu.fenniak.net>", package_info.author)
                self.assertEqual("Martin Thoma <info@martin-thoma.de>", package_info.maintainer)
                self.assertEqual(LICENSE_UNKNOWN, package_info.license)
                self.assertEqual("A pure-python PDF library capable of splitting, merging, cropping, and transforming PDF files", package_info.summary)
                self.assertEqual(["BSD License"], package_info.license_classifiers)
                self.assertIn('black ; extra == "dev"', package_info.requirements)

    def test_get_package_info__normalize_name(self) -> None:
        distribution = DummyDistribution()
        for source, target in [
                ("pypdf", "pypdf"),
                ("WebOb", "webob"),
                ("lxml_html_clean", "lxml-html-clean")
        ]:
            with self.subTest(source=source):
                distribution.metadata["name"] = source
                self.assertEqual(source, get_package_info(distribution, normalize_name=False).name)  # type: ignore[arg-type]
                self.assertEqual(target, get_package_info(distribution, normalize_name=True).name)  # type: ignore[arg-type]

    def test_get_package_info__author_field(self) -> None:
        distribution = DummyDistribution()
        distribution.metadata["author"] = "Max Mustermann"
        distribution.metadata["author-email"] = "max@localhost"
        self.assertEqual("Max Mustermann", get_package_info(distribution).author)  # type: ignore[arg-type]

    def test_get_package_info__author_email_field(self) -> None:
        distribution = DummyDistribution()
        distribution.metadata["author-email"] = "max@localhost"
        self.assertEqual("max@localhost", get_package_info(distribution).author)  # type: ignore[arg-type]

    def test_get_package_info__no_author_field(self) -> None:
        distribution = DummyDistribution()
        self.assertEqual(LICENSE_UNKNOWN, get_package_info(distribution).author)  # type: ignore[arg-type]

    def test_get_package_info__maintainer_field(self) -> None:
        distribution = DummyDistribution()
        distribution.metadata["maintainer"] = "Max Mustermann"
        distribution.metadata["maintainer-email"] = "max@localhost"
        self.assertEqual("Max Mustermann", get_package_info(distribution).maintainer)  # type: ignore[arg-type]

    def test_get_package_info__maintainer_email_field(self) -> None:
        distribution = DummyDistribution()
        distribution.metadata["maintainer-email"] = "max@localhost"
        self.assertEqual("max@localhost", get_package_info(distribution).maintainer)  # type: ignore[arg-type]

    def test_get_package_info__no_maintainer_field(self) -> None:
        distribution = DummyDistribution()
        self.assertEqual(LICENSE_UNKNOWN, get_package_info(distribution).maintainer)  # type: ignore[arg-type]

    def test_get_package_info__file_casing(self) -> None:
        with NamedTemporaryFile(suffix=".zip") as fd:
            response = requests.get(url="https://files.pythonhosted.org/packages/c3/c2/fbc206db211c11ac85f2b440670ff6f43d44d7601f61b95628f56d271c21/WebOb-1.8.8-py2.py3-none-any.whl")  # noqa: E501
            self.assertEqual(200, response.status_code, response)
            fd.write(response.content)
            fd.seek(0)
            with TemporaryDirectory() as directory:
                shutil.unpack_archive(filename=fd.name, extract_dir=directory)
                webob = PathDistribution(Path(directory, "WebOb-1.8.8.dist-info"))
                package_info = get_package_info(webob)
                license_files = list(package_info.license_files)
                self.assertEqual(
                    [str(Path(directory) / "WebOb-1.8.8.dist-info" / "license.txt")],
                    license_files,
                )


class GetPackagesTestCase(TestCase):
    def test_get_packages(self) -> None:
        packages = get_packages(from_source=FromArg.MIXED)
        package_names = set(map(attrgetter("name"), packages))
        for package in ["pip", "pypdf"]:
            self.assertIn(package, package_names)
        # `setuptools` is not being shipped by default anymore since Python 3.12.
        if sys.version_info < (3, 12):
            self.assertIn("setuptools", package_names)
        else:
            self.assertNotIn("setuptools", package_names)

    def test_get_packages__includes_license_names(self) -> None:
        with create_temporary_venv() as venv:
            packages = get_packages(from_source=FromArg.MIXED, python_path=venv.executable)
            license_names = {
                package.name: package.license_names for package in packages
            }

        for package in ["pip"]:
            self.assertTrue(license_names.get(package))
            self.assertIn("MIT License", license_names[package])

        # `setuptools` is not being shipped by default anymore since Python 3.12.
        if sys.version_info < (3, 12):
            self.assertTrue(license_names.get("setuptools"))
            self.assertIn("MIT License", license_names["setuptools"])
        else:
            self.assertFalse(license_names.get("setuptools"))

    def test_get_packages__python_path(self) -> None:
        with create_temporary_venv() as venv:
            packages = get_packages(from_source=FromArg.MIXED, python_path=venv.executable)
            package_names = set(map(attrgetter("name"), packages))

        # `setuptools` is not being shipped by default anymore since Python 3.12.
        if sys.version_info < (3, 12):
            self.assertSetEqual({"pip", "setuptools"}, package_names)
        else:
            self.assertSetEqual({"pip"}, package_names)


class FindLicenseFromClassifier(TestCase):
    def test_find_license_from_classifier__unrelated_classifiers_only(self) -> None:
        classifiers = [
            "Development Status :: 4 - Beta",
            "Environment :: Console",
            "Intended Audience :: Developers",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3 :: Only",
            "Topic :: Software Development",
        ]
        self.assertEqual(
            [],
            find_license_from_classifier(classifiers)
        )

    def test_find_license_from_classifier__one_matching_classifier(self) -> None:
        classifiers = [
            "Development Status :: 4 - Beta",
            "Environment :: Console",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: Apache Software License",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3 :: Only",
            "Topic :: Software Development",
        ]
        self.assertEqual(
            ["Apache Software License"],
            find_license_from_classifier(classifiers)
        )

    def test_find_license_from_classifier(self) -> None:
        classifiers = ["License :: OSI Approved :: MIT License"]
        self.assertEqual(
            ["MIT License"],
            find_license_from_classifier(classifiers)
        )

    def test_find_license_from_classifier__multiple_licenses(self) -> None:
        classifiers = [
            "License :: OSI Approved",
            "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
            "License :: OSI Approved :: MIT License",
            "License :: Public Domain",
        ]
        self.assertEqual(
            [
                "GNU General Public License v3 (GPLv3)",
                "MIT License",
                "Public Domain",
            ],
            find_license_from_classifier(classifiers),
        )

    def test_find_license_from_classifier__no_classifiers(self) -> None:
        classifiers: List[str] = []
        self.assertEqual([], find_license_from_classifier(classifiers))


class SelectLicenseBySourceTestCase(TestCase):
    def test_select_license_by_source(self) -> None:
        self.assertEqual(
            {"MIT License"},
            select_license_by_source(
                FromArg.CLASSIFIER, ["MIT License"], "MIT"
            ),
        )

        self.assertEqual(
            {LICENSE_UNKNOWN},
            select_license_by_source(FromArg.CLASSIFIER, [], "MIT"),
        )

        self.assertEqual(
            {"MIT License"},
            select_license_by_source(FromArg.MIXED, ["MIT License"], "MIT"),
        )

        self.assertEqual(
            {"MIT"}, select_license_by_source(FromArg.MIXED, [], "MIT")
        )
        self.assertEqual(
            {"Apache License 2.0"},
            select_license_by_source(
                FromArg.MIXED, ["Apache License 2.0"], "Apache-2.0"
            ),
        )


class FromArgTestCase(TestCase):
    def test_repr(self) -> None:
        for name in ["META", "CLASSIFIER", "MIXED", "ALL"]:
            with self.subTest(name=name):
                value = getattr(FromArg, name)
                self.assertEqual(f"<FromArg.{name}>", repr(value))
