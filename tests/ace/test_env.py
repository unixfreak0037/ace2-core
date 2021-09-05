import os.path

import pytest

import ace.env
from ace.env import get_uri, get_api_key, get_base_dir, get_package_dir, get_package_manager, register_global_env
from ace.packages.manager import ACEPackageManager


@pytest.mark.unit
def test_operating_env_init_no_args():
    env = ace.env.ACEOperatingEnvironment("")
    assert env.get_uri() is None
    assert env.get_api_key() is None
    # the test environment uses a temporary directory for the base dir
    # so this assertion doesn't work
    # assert env.get_base_dir() == ace.env.get_default_base_dir()
    assert env.get_package_dir() == os.path.join(env.get_base_dir(), "packages")
    assert isinstance(env.get_package_manager(), ACEPackageManager)


@pytest.mark.unit
def test_operating_env_init_env_args(monkeypatch):
    monkeypatch.setenv("ACE_URI", "http://test")
    monkeypatch.setenv("ACE_API_KEY", "test")
    monkeypatch.setenv("ACE_BASE_DIR", "/opt/ace")
    monkeypatch.setenv("ACE_PACKAGE_DIR", "/opt/ace/test/packages")

    env = ace.env.ACEOperatingEnvironment("")
    assert env.get_uri() == "http://test"
    assert env.get_api_key() == "test"
    assert env.get_base_dir() == "/opt/ace"
    assert env.get_package_dir() == "/opt/ace/test/packages"


@pytest.mark.unit
def test_operating_env_init_cli_args(monkeypatch):
    monkeypatch.setenv("ACE_URI", "http://test")
    monkeypatch.setenv("ACE_API_KEY", "test")
    monkeypatch.setenv("ACE_BASE_DIR", "/opt/ace")
    monkeypatch.setenv("ACE_PACKAGE_DIR", "/opt/ace/test/packages")

    env = ace.env.ACEOperatingEnvironment(
        ["-u", "http://test", "-k", "test", "-b", "/opt/ace", "--package-dir", "/opt/ace/test/packages"]
    )
    assert env.get_uri() == "http://test"
    assert env.get_api_key() == "test"
    assert env.get_base_dir() == "/opt/ace"
    assert env.get_package_dir() == "/opt/ace/test/packages"


@pytest.mark.unit
def test_get_env():
    assert isinstance(ace.env.get_env(), ace.env.ACEOperatingEnvironment)


@pytest.mark.unit
def test_shortcut_functions(monkeypatch):
    monkeypatch.setenv("ACE_URI", "http://test")
    monkeypatch.setenv("ACE_API_KEY", "test")
    monkeypatch.setenv("ACE_BASE_DIR", "/opt/ace")
    monkeypatch.setenv("ACE_PACKAGE_DIR", "/opt/ace/test/packages")

    register_global_env(ace.env.ACEOperatingEnvironment(""))
    assert ace.env.get_uri() == get_uri()
    assert ace.env.get_api_key() == get_api_key()
    assert ace.env.get_base_dir() == get_base_dir()
    assert ace.env.get_package_dir() == get_package_dir()
    assert ace.env.get_package_manager() == get_package_manager()
