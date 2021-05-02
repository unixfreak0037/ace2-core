# vim: ts=4:sw=4:et:cc=120

import os
import os.path
import importlib

from dataclasses import dataclass, field
from typing import Optional

from ace.module.base import AnalysisModule
from ace.env import get_package_dir

import yaml


@dataclass
class ACEPackage:
    source: str
    name: str
    description: str
    version: str

    # the list of AnalysisModule types that this package provides
    modules: Optional[type[AnalysisModule]] = field(default_factory=list)


def load_packages(package_dir: Optional[str] = None) -> list[ACEPackage]:
    # if we don't specify the package directories then we use a default
    result = []

    if not package_dir:
        package_dir = get_package_dir()

    for target in os.listdir(package_dir):
        if not target.endswith(".yml"):
            continue

        target = os.path.join(package_dir, target)
        with open(target, "r") as fp:
            package_definition = yaml.load(fp, Loader=yaml.FullLoader)

        _package = ACEPackage(
            source=target,
            name=package_definition["name"],
            description=package_definition["description"],
            version=package_definition["version"],
        )

        if "modules" in package_definition:
            for module_spec in package["modules"]:
                module_name, class_name = module_spec.rsplit(".", 1)
                _module = importlib.import_module(module_name)
                _package.modules.append(getattr(_module, class_name))

        result.append(target)

    return result


def load_package_from_dict(package_definition: dict, source: str) -> ACEPackage:
    _package = ACEPackage(
        source=source,
        name=package_definition["name"],
        description=package_definition["description"],
        version=package_definition["version"],
    )

    # load any defined modules
    if "modules" in package_definition:
        for module_spec in package_definition["modules"]:
            module_name, class_name = module_spec.rsplit(".", 1)
            _module = importlib.import_module(module_name)
            _package.modules.append(getattr(_module, class_name))

    return _package


def load_package_from_yaml(path: str) -> ACEPackage:
    with open(path, "r") as fp:
        package_definition = yaml.load(fp, Loader=yaml.FullLoader)

    return load_package_from_dict(package_definition, path)
