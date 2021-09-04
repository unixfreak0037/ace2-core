# vim: sw=4:ts=4:et:cc=120

import os
import os.path

import pytest
import yaml

import ace.env

from ace.module.base import AnalysisModule
from ace.packages import ACEPackage, get_package_manager
from ace.service.base import ACEService


class TestModule1(AnalysisModule):
    __test__ = False


class TestModule2(AnalysisModule):
    __test__ = False


class TestService1(ACEService):
    __test__ = False
    name = "test_1"


class TestService2(ACEService):
    __test__ = False
    name = "test_2"


sample_yaml = """
---
  name: Sample Package
  description: Sample Description
  version: 1.0.0

  modules:
    - tests.ace.test_packages.TestModule1
    - tests.ace.test_packages.TestModule2

  services:
    - tests.ace.test_packages.TestService1
    - tests.ace.test_packages.TestService2

  config:
    core_modules:
      file_analysis:
        file_type:
          file_path:
            value: file
            description: Path to the file binary.
          some_param: 
            value: some_value
            description: A good description people can understand.
        file_hash:
          some_param: other_value # no value or key, so it just defaults to an empty description
      url_analysis:
        crawlphish:
          max_requests:
            value: 4096
            description: Maximum number of simultaneous requests.
          max_size: 
            value: 35 MB
            description: >
              Maximum size of data downloaded from target URL. 
              An value by itself is interpreted as bytes.
              You can also specify KB, MB or GB.
          use_proxy: False
          use_tor: False
          # this stuff maps into the configuration settings like this:
          # /core_modules/url_analysis/crawlphish/max_requests
          # /core_modules/url_analysis/crawlphish/use_proxy
          # /core_modules/url_analysis/crawlphish/use_tor
          # /core_modules/url_analysis/crawlphish/custom_headers
          custom_headers:
            - "User-Agent: blah blah blah"
            - "Some-Header: blah blah boo"
"""


def verify_loaded_package(package: ACEPackage):
    assert isinstance(package, ACEPackage)
    # assert package.source == "test"
    assert package.name == "Sample Package"
    assert package.description == "Sample Description"
    assert package.version == "1.0.0"
    assert len(package.modules) == 2
    for i in range(2):
        assert issubclass(package.modules[i], AnalysisModule)
        module_instance = package.modules[i]()
        assert isinstance(module_instance, AnalysisModule)

    assert len(package.services) == 2
    for i in range(2):
        assert issubclass(package.services[i], ACEService)
        service_instance = package.services[i]()
        assert isinstance(service_instance, ACEService)


@pytest.mark.unit
def test_load_package_from_dict():
    verify_loaded_package(get_package_manager().load_package_from_dict(yaml.safe_load(sample_yaml), "test"))


@pytest.mark.unit
def test_load_packages(tmpdir):
    package_dir = str(tmpdir / "packages")
    os.mkdir(package_dir)
    path = os.path.join(package_dir, "test.yml")

    with open(path, "w") as fp:
        fp.write(sample_yaml)

    packages = get_package_manager().load_packages(package_dir)
    assert len(packages) == 1
    verify_loaded_package(packages[0])
