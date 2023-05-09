from copy import deepcopy

import unittest
from unittest import mock

import dbt.deps
import dbt.exceptions
from dbt.deps.git import GitUnpinnedPackage
from dbt.deps.local import LocalUnpinnedPackage
from dbt.deps.tarball import TarballUnpinnedPackage
from dbt.deps.registry import RegistryUnpinnedPackage
from dbt.clients.registry import is_compatible_version
from dbt.deps.resolver import resolve_packages
from dbt.contracts.project import (
    LocalPackage,
    TarballPackage,
    GitPackage,
    RegistryPackage,
)
from dbt.contracts.project import PackageConfig
from dbt.semver import VersionSpecifier
from dbt.version import get_installed_version

from dbt.dataclass_schema import ValidationError


class TestLocalPackage(unittest.TestCase):
    def test_init(self):
        a_contract = LocalPackage.from_dict({"local": "/path/to/package"})
        self.assertEqual(a_contract.local, "/path/to/package")
        a = LocalUnpinnedPackage.from_contract(a_contract)
        self.assertEqual(a.local, "/path/to/package")
        a_pinned = a.resolved()
        self.assertEqual(a_pinned.local, "/path/to/package")
        self.assertEqual(str(a_pinned), "/path/to/package")


class TestTarballPackage(unittest.TestCase):
    def test_TarballPackage(self):
        from dbt.contracts.project import RegistryPackageMetadata
        from mashumaro.exceptions import MissingField

        dict_well_formed_contract = {"tarball": "http://example.com", "name": "my_cool_package"}

        a_contract = TarballPackage.from_dict(dict_well_formed_contract)

        # check contract and resolver
        self.assertEqual(a_contract.tarball, "http://example.com")
        self.assertEqual(a_contract.name, "my_cool_package")

        a = TarballUnpinnedPackage.from_contract(a_contract)
        self.assertEqual(a.tarball, "http://example.com")
        self.assertEqual(a.package, "my_cool_package")

        a_pinned = a.resolved()
        self.assertEqual(a_pinned.source_type(), "tarball")

        # check bad contract (no name) fails
        dict_missing_name_should_fail_on_contract = {"tarball": "http://example.com"}

        with self.assertRaises(MissingField):
            TarballPackage.from_dict(dict_missing_name_should_fail_on_contract)

        # check RegistryPackageMetadata - it is used in TarballUnpinnedPackage
        dct = {
            "name": a.package,
            "packages": [],  # note: required by RegistryPackageMetadata
            "downloads": {"tarball": a_pinned.tarball},
        }

        metastore = RegistryPackageMetadata.from_dict(dct)
        self.assertEqual(metastore.downloads.tarball, "http://example.com")


class TestGitPackage(unittest.TestCase):
    def test_init(self):
        a_contract = GitPackage.from_dict(
            {"git": "http://example.com", "revision": "0.0.1"},
        )
        self.assertEqual(a_contract.git, "http://example.com")
        self.assertEqual(a_contract.revision, "0.0.1")
        self.assertIs(a_contract.warn_unpinned, None)

        a = GitUnpinnedPackage.from_contract(a_contract)
        self.assertEqual(a.git, "http://example.com")
        self.assertEqual(a.revisions, ["0.0.1"])
        self.assertIs(a.warn_unpinned, True)

        a_pinned = a.resolved()
        self.assertEqual(a_pinned.name, "http://example.com")
        self.assertEqual(a_pinned.get_version(), "0.0.1")
        self.assertEqual(a_pinned.source_type(), "git")
        self.assertIs(a_pinned.warn_unpinned, True)

    def test_invalid(self):
        with self.assertRaises(ValidationError):
            GitPackage.validate(
                {"git": "http://example.com", "version": "0.0.1"},
            )

    def test_resolve_ok(self):
        a_contract = GitPackage.from_dict(
            {"git": "http://example.com", "revision": "0.0.1"},
        )
        b_contract = GitPackage.from_dict(
            {"git": "http://example.com", "revision": "0.0.1", "warn-unpinned": False},
        )
        a = GitUnpinnedPackage.from_contract(a_contract)
        b = GitUnpinnedPackage.from_contract(b_contract)
        self.assertTrue(a.warn_unpinned)
        self.assertFalse(b.warn_unpinned)
        c = a.incorporate(b)

        c_pinned = c.resolved()
        self.assertEqual(c_pinned.name, "http://example.com")
        self.assertEqual(c_pinned.get_version(), "0.0.1")
        self.assertEqual(c_pinned.source_type(), "git")
        self.assertFalse(c_pinned.warn_unpinned)

    def test_resolve_fail(self):
        a_contract = GitPackage.from_dict(
            {"git": "http://example.com", "revision": "0.0.1"},
        )
        b_contract = GitPackage.from_dict(
            {"git": "http://example.com", "revision": "0.0.2"},
        )
        a = GitUnpinnedPackage.from_contract(a_contract)
        b = GitUnpinnedPackage.from_contract(b_contract)
        c = a.incorporate(b)
        self.assertEqual(c.git, "http://example.com")
        self.assertEqual(c.revisions, ["0.0.1", "0.0.2"])

        with self.assertRaises(dbt.exceptions.DependencyError):
            c.resolved()

    def test_default_revision(self):
        a_contract = GitPackage.from_dict({"git": "http://example.com"})
        self.assertEqual(a_contract.revision, None)
        self.assertIs(a_contract.warn_unpinned, None)

        a = GitUnpinnedPackage.from_contract(a_contract)
        self.assertEqual(a.git, "http://example.com")
        self.assertEqual(a.revisions, [])
        self.assertIs(a.warn_unpinned, True)

        a_pinned = a.resolved()
        self.assertEqual(a_pinned.name, "http://example.com")
        self.assertEqual(a_pinned.get_version(), "HEAD")
        self.assertEqual(a_pinned.source_type(), "git")
        self.assertIs(a_pinned.warn_unpinned, True)


class TestHubPackage(unittest.TestCase):
    def setUp(self):
        self.patcher = mock.patch("dbt.deps.registry.registry")
        self.registry = self.patcher.start()
        self.index_cached = self.registry.index_cached
        self.get_compatible_versions = self.registry.get_compatible_versions
        self.package_version = self.registry.package_version

        self.index_cached.return_value = [
            "dbt-labs-test/a",
        ]
        self.get_compatible_versions.return_value = ["0.1.2", "0.1.3", "0.1.4a1"]
        self.package_version.return_value = {
            "id": "dbt-labs-test/a/0.1.2",
            "name": "a",
            "version": "0.1.2",
            "packages": [],
            "_source": {
                "blahblah": "asdfas",
            },
            "downloads": {
                "tarball": "https://example.com/invalid-url!",
                "extra": "field",
            },
            "newfield": ["another", "value"],
        }

    def tearDown(self):
        self.patcher.stop()

    def test_init(self):
        a_contract = RegistryPackage(
            package="dbt-labs-test/a",
            version="0.1.2",
        )
        self.assertEqual(a_contract.package, "dbt-labs-test/a")
        self.assertEqual(a_contract.version, "0.1.2")

        a = RegistryUnpinnedPackage.from_contract(a_contract)
        self.assertEqual(a.package, "dbt-labs-test/a")
        self.assertEqual(
            a.versions,
            [
                VersionSpecifier(
                    build=None, major="0", matcher="=", minor="1", patch="2", prerelease=None
                )
            ],
        )

        a_pinned = a.resolved()
        self.assertEqual(a_contract.package, "dbt-labs-test/a")
        self.assertEqual(a_contract.version, "0.1.2")
        self.assertEqual(a_pinned.source_type(), "hub")

    def test_invalid(self):
        with self.assertRaises(ValidationError):
            RegistryPackage.validate(
                {"package": "namespace/name", "key": "invalid"},
            )

    def test_resolve_ok(self):
        a_contract = RegistryPackage(package="dbt-labs-test/a", version="0.1.2")
        b_contract = RegistryPackage(package="dbt-labs-test/a", version="0.1.2")
        a = RegistryUnpinnedPackage.from_contract(a_contract)
        b = RegistryUnpinnedPackage.from_contract(b_contract)
        c = a.incorporate(b)

        self.assertEqual(c.package, "dbt-labs-test/a")
        self.assertEqual(
            c.versions,
            [
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher="=",
                    minor="1",
                    patch="2",
                    prerelease=None,
                ),
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher="=",
                    minor="1",
                    patch="2",
                    prerelease=None,
                ),
            ],
        )

        c_pinned = c.resolved()
        self.assertEqual(c_pinned.package, "dbt-labs-test/a")
        self.assertEqual(c_pinned.version, "0.1.2")
        self.assertEqual(c_pinned.source_type(), "hub")

    def test_resolve_missing_package(self):
        a = RegistryUnpinnedPackage.from_contract(
            RegistryPackage(package="dbt-labs-test/b", version="0.1.2")
        )
        with self.assertRaises(dbt.exceptions.DependencyError) as exc:
            a.resolved()

        msg = "Package dbt-labs-test/b was not found in the package index"
        self.assertEqual(msg, str(exc.exception))

    def test_resolve_missing_version(self):
        a = RegistryUnpinnedPackage.from_contract(
            RegistryPackage(package="dbt-labs-test/a", version="0.1.4")
        )

        with self.assertRaises(dbt.exceptions.DependencyError) as exc:
            a.resolved()
        msg = (
            "Could not find a matching compatible version for package "
            "dbt-labs-test/a\n  Requested range: =0.1.4, =0.1.4\n  "
            "Compatible versions: ['0.1.2', '0.1.3']\n"
        )
        assert msg in str(exc.exception)

    def test_resolve_conflict(self):
        a_contract = RegistryPackage(package="dbt-labs-test/a", version="0.1.2")
        b_contract = RegistryPackage(package="dbt-labs-test/a", version="0.1.3")
        a = RegistryUnpinnedPackage.from_contract(a_contract)
        b = RegistryUnpinnedPackage.from_contract(b_contract)
        c = a.incorporate(b)

        with self.assertRaises(dbt.exceptions.DependencyError) as exc:
            c.resolved()
        msg = (
            "Version error for package dbt-labs-test/a: Could not "
            "find a satisfactory version from options: ['=0.1.2', '=0.1.3']"
        )
        self.assertEqual(msg, str(exc.exception))

    def test_resolve_ranges(self):
        a_contract = RegistryPackage(package="dbt-labs-test/a", version="0.1.2")
        b_contract = RegistryPackage(package="dbt-labs-test/a", version="<0.1.4")
        a = RegistryUnpinnedPackage.from_contract(a_contract)
        b = RegistryUnpinnedPackage.from_contract(b_contract)
        c = a.incorporate(b)

        self.assertEqual(c.package, "dbt-labs-test/a")
        self.assertEqual(
            c.versions,
            [
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher="=",
                    minor="1",
                    patch="2",
                    prerelease=None,
                ),
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher="<",
                    minor="1",
                    patch="4",
                    prerelease=None,
                ),
            ],
        )

        c_pinned = c.resolved()
        self.assertEqual(c_pinned.package, "dbt-labs-test/a")
        self.assertEqual(c_pinned.version, "0.1.2")
        self.assertEqual(c_pinned.source_type(), "hub")

    def test_resolve_ranges_install_prerelease_default_false(self):
        a_contract = RegistryPackage(package="dbt-labs-test/a", version=">0.1.2")
        b_contract = RegistryPackage(package="dbt-labs-test/a", version="<0.1.5")
        a = RegistryUnpinnedPackage.from_contract(a_contract)
        b = RegistryUnpinnedPackage.from_contract(b_contract)
        c = a.incorporate(b)

        self.assertEqual(c.package, "dbt-labs-test/a")
        self.assertEqual(
            c.versions,
            [
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher=">",
                    minor="1",
                    patch="2",
                    prerelease=None,
                ),
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher="<",
                    minor="1",
                    patch="5",
                    prerelease=None,
                ),
            ],
        )

        c_pinned = c.resolved()
        self.assertEqual(c_pinned.package, "dbt-labs-test/a")
        self.assertEqual(c_pinned.version, "0.1.3")
        self.assertEqual(c_pinned.source_type(), "hub")

    def test_resolve_ranges_install_prerelease_true(self):
        a_contract = RegistryPackage(
            package="dbt-labs-test/a", version=">0.1.2", install_prerelease=True
        )
        b_contract = RegistryPackage(package="dbt-labs-test/a", version="<0.1.5")
        a = RegistryUnpinnedPackage.from_contract(a_contract)
        b = RegistryUnpinnedPackage.from_contract(b_contract)
        c = a.incorporate(b)

        self.assertEqual(c.package, "dbt-labs-test/a")
        self.assertEqual(
            c.versions,
            [
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher=">",
                    minor="1",
                    patch="2",
                    prerelease=None,
                ),
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher="<",
                    minor="1",
                    patch="5",
                    prerelease=None,
                ),
            ],
        )

        c_pinned = c.resolved()
        self.assertEqual(c_pinned.package, "dbt-labs-test/a")
        self.assertEqual(c_pinned.version, "0.1.4a1")
        self.assertEqual(c_pinned.source_type(), "hub")

    def test_get_version_latest_prelease_true(self):
        a_contract = RegistryPackage(
            package="dbt-labs-test/a", version=">0.1.0", install_prerelease=True
        )
        b_contract = RegistryPackage(package="dbt-labs-test/a", version="<0.1.4")
        a = RegistryUnpinnedPackage.from_contract(a_contract)
        b = RegistryUnpinnedPackage.from_contract(b_contract)
        c = a.incorporate(b)

        self.assertEqual(c.package, "dbt-labs-test/a")
        self.assertEqual(
            c.versions,
            [
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher=">",
                    minor="1",
                    patch="0",
                    prerelease=None,
                ),
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher="<",
                    minor="1",
                    patch="4",
                    prerelease=None,
                ),
            ],
        )

        c_pinned = c.resolved()
        self.assertEqual(c_pinned.package, "dbt-labs-test/a")
        self.assertEqual(c_pinned.version, "0.1.3")
        self.assertEqual(c_pinned.get_version_latest(), "0.1.4a1")
        self.assertEqual(c_pinned.source_type(), "hub")

    def test_get_version_latest_prelease_false(self):
        a_contract = RegistryPackage(
            package="dbt-labs-test/a", version=">0.1.0", install_prerelease=False
        )
        b_contract = RegistryPackage(package="dbt-labs-test/a", version="<0.1.4")
        a = RegistryUnpinnedPackage.from_contract(a_contract)
        b = RegistryUnpinnedPackage.from_contract(b_contract)
        c = a.incorporate(b)

        self.assertEqual(c.package, "dbt-labs-test/a")
        self.assertEqual(
            c.versions,
            [
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher=">",
                    minor="1",
                    patch="0",
                    prerelease=None,
                ),
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher="<",
                    minor="1",
                    patch="4",
                    prerelease=None,
                ),
            ],
        )

        c_pinned = c.resolved()
        self.assertEqual(c_pinned.package, "dbt-labs-test/a")
        self.assertEqual(c_pinned.version, "0.1.3")
        self.assertEqual(c_pinned.get_version_latest(), "0.1.3")
        self.assertEqual(c_pinned.source_type(), "hub")

    def test_get_version_prerelease_explicitly_requested(self):
        a_contract = RegistryPackage(
            package="dbt-labs-test/a", version="0.1.4a1", install_prerelease=None
        )

        a = RegistryUnpinnedPackage.from_contract(a_contract)

        self.assertEqual(a.package, "dbt-labs-test/a")
        self.assertEqual(
            a.versions,
            [
                VersionSpecifier(
                    build=None,
                    major="0",
                    matcher="=",
                    minor="1",
                    patch="4",
                    prerelease="a1",
                ),
            ],
        )

        a_pinned = a.resolved()
        self.assertEqual(a_pinned.package, "dbt-labs-test/a")
        self.assertEqual(a_pinned.version, "0.1.4a1")
        self.assertEqual(a_pinned.get_version_latest(), "0.1.4a1")
        self.assertEqual(a_pinned.source_type(), "hub")


class MockRegistry:
    def __init__(self, packages):
        self.packages = packages

    def index_cached(self, registry_base_url=None):
        return sorted(self.packages)

    def package(self, package_name, registry_base_url=None):
        try:
            pkg = self.packages[package_name]
        except KeyError:
            return []
        return pkg

    def get_compatible_versions(self, package_name, dbt_version, should_version_check):
        packages = self.package(package_name)
        return [
            pkg_version
            for pkg_version, info in packages.items()
            if is_compatible_version(info, dbt_version)
        ]

    def package_version(self, name, version):
        try:
            return self.packages[name][version]
        except KeyError:
            return None


class TestPackageSpec(unittest.TestCase):
    def setUp(self):
        dbt_version = get_installed_version()
        next_version = deepcopy(dbt_version)
        next_version.minor = str(int(next_version.minor) + 1)
        next_version.prerelease = None
        require_next_version = ">" + next_version.to_version_string()

        self.patcher = mock.patch("dbt.deps.registry.registry")
        self.registry = self.patcher.start()
        self.mock_registry = MockRegistry(
            packages={
                "dbt-labs-test/a": {
                    "0.1.2": {
                        "id": "dbt-labs-test/a/0.1.2",
                        "name": "a",
                        "version": "0.1.2",
                        "packages": [],
                        "_source": {
                            "blahblah": "asdfas",
                        },
                        "downloads": {
                            "tarball": "https://example.com/invalid-url!",
                            "extra": "field",
                        },
                        "newfield": ["another", "value"],
                    },
                    "0.1.3": {
                        "id": "dbt-labs-test/a/0.1.3",
                        "name": "a",
                        "version": "0.1.3",
                        "packages": [],
                        "_source": {
                            "blahblah": "asdfas",
                        },
                        "downloads": {
                            "tarball": "https://example.com/invalid-url!",
                            "extra": "field",
                        },
                        "newfield": ["another", "value"],
                    },
                    "0.1.4a1": {
                        "id": "dbt-labs-test/a/0.1.3a1",
                        "name": "a",
                        "version": "0.1.4a1",
                        "packages": [],
                        "_source": {
                            "blahblah": "asdfas",
                        },
                        "downloads": {
                            "tarball": "https://example.com/invalid-url!",
                            "extra": "field",
                        },
                        "newfield": ["another", "value"],
                    },
                    "0.2.0": {
                        "id": "dbt-labs-test/a/0.2.0",
                        "name": "a",
                        "version": "0.2.0",
                        "packages": [],
                        "_source": {
                            "blahblah": "asdfas",
                        },
                        # this one shouldn't be picked!
                        "require_dbt_version": require_next_version,
                        "downloads": {
                            "tarball": "https://example.com/invalid-url!",
                            "extra": "field",
                        },
                        "newfield": ["another", "value"],
                    },
                },
                "dbt-labs-test/b": {
                    "0.2.1": {
                        "id": "dbt-labs-test/b/0.2.1",
                        "name": "b",
                        "version": "0.2.1",
                        "packages": [{"package": "dbt-labs-test/a", "version": ">=0.1.3"}],
                        "_source": {
                            "blahblah": "asdfas",
                        },
                        "downloads": {
                            "tarball": "https://example.com/invalid-url!",
                            "extra": "field",
                        },
                        "newfield": ["another", "value"],
                    },
                },
            }
        )

        self.registry.index_cached.side_effect = self.mock_registry.index_cached
        self.registry.get_compatible_versions.side_effect = (
            self.mock_registry.get_compatible_versions
        )
        self.registry.package_version.side_effect = self.mock_registry.package_version

    def tearDown(self):
        self.patcher.stop()

    def test_dependency_resolution(self):
        package_config = PackageConfig.from_dict(
            {
                "packages": [
                    {"package": "dbt-labs-test/a", "version": ">0.1.2"},
                    {"package": "dbt-labs-test/b", "version": "0.2.1"},
                ],
            }
        )
        resolved = resolve_packages(
            package_config.packages, mock.MagicMock(project_name="test"), {}
        )
        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0].name, "dbt-labs-test/a")
        self.assertEqual(resolved[0].version, "0.1.3")
        self.assertEqual(resolved[1].name, "dbt-labs-test/b")
        self.assertEqual(resolved[1].version, "0.2.1")

    def test_dependency_resolution_allow_prerelease(self):
        package_config = PackageConfig.from_dict(
            {
                "packages": [
                    {
                        "package": "dbt-labs-test/a",
                        "version": ">0.1.2",
                        "install_prerelease": True,
                    },
                    {"package": "dbt-labs-test/b", "version": "0.2.1"},
                ],
            }
        )
        resolved = resolve_packages(
            package_config.packages, mock.MagicMock(project_name="test"), {}
        )
        self.assertEqual(resolved[0].name, "dbt-labs-test/a")
        self.assertEqual(resolved[0].version, "0.1.4a1")

    def test_validation_error_when_version_is_missing_from_package_config(self):

        packages_data = {"packages": [{"package": "dbt-labs-test/b", "version": None}]}

        with self.assertRaises(ValidationError) as exc:
            PackageConfig.validate(data=packages_data)

        msg = "dbt-labs-test/b is missing the version. When installing from the Hub package index, version is a required property"
        assert msg in str(exc.exception)

    def test_validation_error_when_namespace_is_missing_from_package_config(self):

        packages_data = {"packages": [{"package": "dbt-labs", "version": "1.0.0"}]}

        with self.assertRaises(ValidationError) as exc:
            PackageConfig.validate(data=packages_data)

        msg = "dbt-labs was not found in the package index. Packages on the index require a namespace, e.g dbt-labs/dbt_utils"
        assert msg in str(exc.exception)
