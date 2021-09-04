# vim: ts=4:sw=4:et:cc=120

import os
import os.path
import importlib

from dataclasses import dataclass, field
from typing import Optional

import ace.env
from ace.logging import get_logger
from ace.module.base import AnalysisModule
from ace.packages.package import ACEPackage
from ace.service.base import ACEService

import yaml


class ACEPackageManager:
    """Utility class that maintains the list of available packages."""

    def __init__(self):
        # the list of available packages
        self.packages = []

    @property
    def modules(self) -> list[type[AnalysisModule]]:
        """Returns the list of all available AnalysisModule types."""
        result = []
        for package in self.packages:
            result.extend(package.modules)

        return result

    @property
    def services(self) -> list[type[ACEService]]:
        """Returns the list of all available ACEService types."""
        result = []
        for package in self.packages:
            result.extend(package.services)

        return result

    def load_packages(self, package_dir: Optional[str] = None) -> list[ACEPackage]:
        # if we don't specify the package directories then we use a default
        self.packages = []

        if not package_dir:
            package_dir = ace.env.get_env().get_package_dir()

        if not os.path.isdir(package_dir):
            return []

        for target in os.listdir(package_dir):
            if not target.endswith(".yml") and not target.endswith(".yaml"):
                continue

            target = os.path.join(package_dir, target)
            with open(target, "r") as fp:
                package_definition = yaml.load(fp, Loader=yaml.FullLoader)

            self.packages.append(self.load_package_from_dict(package_definition, target))

        return self.packages

    def load_package_from_dict(self, package_definition: dict, source: str) -> ACEPackage:
        _package = ACEPackage(
            source=source,
            name=package_definition["name"],
            description=package_definition["description"],
            version=package_definition["version"],
        )

        get_logger().debug(f"loading package from {source}")

        # load any defined modules
        if "modules" in package_definition:
            for module_spec in package_definition["modules"]:
                module_name, class_name = module_spec.rsplit(".", 1)
                _module = importlib.import_module(module_name)
                _package.modules.append(getattr(_module, class_name))

        # load any defined services
        if "services" in package_definition:
            for service_spec in package_definition["services"]:
                module_name, class_name = service_spec.rsplit(".", 1)
                _module = importlib.import_module(module_name)
                _type = getattr(_module, class_name)
                # sanity check type definition
                if not issubclass(_type, ACEService):
                    raise RuntimeError(f"service definition {service_spec} in {source} does not extend ACEService")

                _package.services.append(_type)

        return _package

    def load_package_from_yaml(self, path: str) -> ACEPackage:
        with open(path, "r") as fp:
            package_definition = yaml.load(fp, Loader=yaml.FullLoader)

        return self.load_package_from_dict(package_definition, path)

    def load_cli_commands(self, parser, subparsers):
        # TODO
        pass


def get_package_manager() -> ACEPackageManager:
    return ace.env.get_env().get_package_manager()
