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
# TODO: Enable and change type hints accordingly after dropping suppor for Python < 3.8.
# from __future__ import annotations

import subprocess
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from types import SimpleNamespace
from typing import Generator, List, Optional
from unittest import TestCase
from unittest.mock import MagicMock
from venv import EnvBuilder as _EnvBuilder

from piplicenses_lib import Distribution, extract_homepage, find_license_from_classifier, FromArg, get_packages, get_package_included_files, \
    get_package_info, LICENSE_UNKNOWN, normalize_package_name, read_file, select_license_by_source
from requests.utils import CaseInsensitiveDict


class EnvBuilder(_EnvBuilder):
    context = None
    executable = None

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
    def test_extract_homepage__home_page_set(self):
        metadata = MagicMock()
        metadata.get.return_value = "Foobar"
        self.assertEqual("Foobar", extract_homepage(metadata=metadata))  # type: ignore

        metadata.get.assert_called_once_with("home-page", None)

    def test_extract_homepage__project_url_fallback(self):
        metadata = MagicMock()
        metadata.get.return_value = None

        # `Homepage` is prioritized higher than `Source`
        metadata.get_all.return_value = [
            "Source, source",
            "Homepage, homepage",
        ]

        self.assertEqual("homepage", extract_homepage(metadata=metadata))  # type: ignore

        metadata.get_all.assert_called_once_with("Project-URL", [])

    def test_extract_homepage__project_url_fallback__multiple_parts(self):
        metadata = MagicMock()
        metadata.get.return_value = None

        # `Homepage` is prioritized higher than `Source`
        metadata.get_all.return_value = [
            "Source, source",
            "Homepage, homepage, foo, bar",
        ]

        self.assertEqual("homepage, foo, bar", extract_homepage(metadata=metadata))  # type: ignore

        metadata.get_all.assert_called_once_with("Project-URL", [])

    def test_extract_homepage__empty(self):
        metadata = MagicMock()

        metadata.get.return_value = None
        metadata.get_all.return_value = []

        self.assertIsNone(extract_homepage(metadata=metadata))  # type: ignore

        metadata.get.assert_called_once_with("home-page", None)
        metadata.get_all.assert_called_once_with("Project-URL", [])

    def test_extract_homepage__project_url_fallback__capitalisation(self):
        metadata = MagicMock()
        metadata.get.return_value = None

        # `homepage` is still prioritized higher than `Source` (capitalisation)
        metadata.get_all.return_value = [
            "Source, source",
            "homepage, homepage",
        ]

        self.assertEqual("homepage", extract_homepage(metadata=metadata))  # type: ignore

        metadata.get_all.assert_called_once_with("Project-URL", [])


class NormalizePackageNameTestCase(TestCase):
    def test_normalize_package_name(self):
        expected_normalized_name = "pip-licenses"

        for name in ["pip_licenses", "pip.licenses", "Pip-Licenses"]:
            with self.subTest(name=name):
                self.assertEqual(expected_normalized_name, normalize_package_name(name))


class ReadFileTestCase(TestCase):
    def test_read_file__regular(self):
        with NamedTemporaryFile(mode="w+t") as fd:
            fd.write("Test text\nabc\n")
            fd.seek(0)
            for path in [fd.name, Path(fd.name)]:
                with self.subTest(path=path):
                    self.assertEqual("Test text\nabc\n", read_file(path))

    def test_read_file__replace(self):
        with NamedTemporaryFile(mode="w+b") as fd:
            fd.write(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x42abc123")
            fd.seek(0)
            self.assertEqual("\x00\x01\x02\x03\x04\x05\x06\x07\x08\tBabc123", read_file(fd.name))


class GetPackageIncludedFilesTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pypdf = Distribution.from_name("pypdf")

    def test_get_package_included_files__no_match(self):
        results = list(get_package_included_files(package=self.pypdf, file_names_regex="MY_INVALID_FILE*"))
        self.assertListEqual([], results)

    def test_get_package_included_file__one_match(self):
        results = list(get_package_included_files(package=self.pypdf, file_names_regex=r"pagerange\.py"))
        self.assertEqual(1, len(results), results)
        self.assertEqual(str(self.pypdf.locate_file("pypdf/pagerange.py")), results[0][0])
        self.assertIn("Representation and utils for ranges of PDF file pages.\n", results[0][1])

    def test_get_package_included_file__multiple_matches(self):
        results = list(get_package_included_files(package=self.pypdf, file_names_regex=r"_.*\.py"))
        self.assertLessEqual(1, len(results), results)
        paths = {result[0] for result in results}
        self.assertIn(
            str(self.pypdf.locate_file("pypdf/_encryption.py")),
            paths
        )


class DummyDistribution:
    class MyDict(CaseInsensitiveDict):
        def get_all(self, key, default=None):
            value = self.get(key, default=default)
            if not isinstance(value, list):
                raise ValueError("get_all called for non-list value")
            return value

    def __init__(self, name="dummy", version="42"):
        self.metadata = self.MyDict(name=name)
        self.files = []
        self.version = version
        self.requires = []


class GetPackageInfoTestCase(TestCase):
    def assertStartsWith(self, expected, actual, message=None):  # noqa: N802
        self.assertEqual(expected, actual[:len(expected)], message)

    def assertEndsWith(self, expected, actual, message=None):  # noqa: N802
        self.assertEqual(expected, actual[-len(expected):], message)

    def test_get_package_info(self):
        import pypdf
        version = pypdf.__version__

        distribution = Distribution.from_name("pypdf")
        package_info = get_package_info(distribution)
        self.assertEqual("pypdf", package_info["name"])
        self.assertEqual(version, package_info["version"])
        self.assertEqual(f"pypdf {version}", package_info["namever"])
        self.assertEqual(1, len(package_info["licensefile"]), package_info["licensefile"])
        self.assertEndsWith(".dist-info/LICENSE", package_info["licensefile"][0])
        self.assertEqual(1, len(package_info["licensetext"]), package_info["licensetext"])
        self.assertStartsWith("Copyright (c) 2006-2008, Mathieu Fenniak\nSome contributions copyright (c) 2007, Ashish", package_info["licensetext"][0])
        self.assertEndsWith(", EVEN IF ADVISED OF THE\nPOSSIBILITY OF SUCH DAMAGE.\n", package_info["licensetext"][0])
        self.assertEqual(0, len(package_info["noticefile"]), package_info["noticefile"])
        self.assertEqual(0, len(package_info["noticetext"]), package_info["noticetext"])
        self.assertIs(distribution, package_info["distribution"])
        self.assertEqual("https://github.com/py-pdf/pypdf", package_info["home-page"])
        self.assertEqual("Mathieu Fenniak <biziqe@mathieu.fenniak.net>", package_info["author"])
        self.assertEqual("Martin Thoma <info@martin-thoma.de>", package_info["maintainer"])
        self.assertEqual(LICENSE_UNKNOWN, package_info["license"])
        self.assertEqual("A pure-python PDF library capable of splitting, merging, cropping, and transforming PDF files", package_info["summary"])
        self.assertEqual(["BSD License"], package_info["license_classifier"])
        self.assertIn('black ; extra == "dev"', package_info["requires"])

    def test_get_package_info__author_field(self):
        distribution = DummyDistribution()
        distribution.metadata["author"] = "Max Mustermann"
        distribution.metadata["author-email"] = "max@localhost"
        self.assertEqual("Max Mustermann", get_package_info(distribution)["author"])  # type: ignore

    def test_get_package_info__author_email_field(self):
        distribution = DummyDistribution()
        distribution.metadata["author-email"] = "max@localhost"
        self.assertEqual("max@localhost", get_package_info(distribution)["author"])  # type: ignore

    def test_get_package_info__no_author_field(self):
        distribution = DummyDistribution()
        self.assertEqual(LICENSE_UNKNOWN, get_package_info(distribution)["author"])  # type: ignore

    def test_get_package_info__maintainer_field(self):
        distribution = DummyDistribution()
        distribution.metadata["maintainer"] = "Max Mustermann"
        distribution.metadata["maintainer-email"] = "max@localhost"
        self.assertEqual("Max Mustermann", get_package_info(distribution)["maintainer"])  # type: ignore

    def test_get_package_info__maintainer_email_field(self):
        distribution = DummyDistribution()
        distribution.metadata["maintainer-email"] = "max@localhost"
        self.assertEqual("max@localhost", get_package_info(distribution)["maintainer"])  # type: ignore

    def test_get_package_info__no_maintainer_field(self):
        distribution = DummyDistribution()
        self.assertEqual(LICENSE_UNKNOWN, get_package_info(distribution)["maintainer"])  # type: ignore


class GetPackagesTestCase(TestCase):
    def test_get_packages(self):
        packages = get_packages(from_source=FromArg.MIXED)
        package_names = {package["name"] for package in packages}
        for package in ["pip", "setuptools", "pypdf"]:
            self.assertIn(package, package_names)

    def test_get_packages__includes_license_names(self):
        with create_temporary_venv() as venv:
            packages = get_packages(from_source=FromArg.MIXED, python_path=venv.executable)
            license_names = {package["name"]: package.get("license_names") for package in packages}

        for package in ["pip", "setuptools"]:
            self.assertTrue(license_names.get(package))
            self.assertIn("MIT License", license_names.get(package))

    def test_get_packages__python_path(self):
        with create_temporary_venv() as venv:
            packages = get_packages(from_source=FromArg.MIXED, python_path=venv.executable)
            package_names = {package["name"] for package in packages}

        self.assertSetEqual({"pip", "setuptools"}, package_names)


class FindLicenseFromClassifier(TestCase):
    def test_find_license_from_classifier__unrelated_classifiers_only(self):
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

    def test_find_license_from_classifier__one_matching_classifier(self):
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

    def test_find_license_from_classifier(self):
        classifiers = ["License :: OSI Approved :: MIT License"]
        self.assertEqual(
            ["MIT License"],
            find_license_from_classifier(classifiers)
        )

    def test_find_license_from_classifier__multiple_licenses(self):
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

    def test_find_license_from_classifier__no_classifiers(self):
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
    def test_repr(self):
        for name in ["META", "CLASSIFIER", "MIXED", "ALL"]:
            with self.subTest(name=name):
                value = getattr(FromArg, name)
                self.assertEqual(f"<FromArg.{name}>", repr(value))
