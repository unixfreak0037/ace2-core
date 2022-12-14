# vim: ts=4:sw=4:et:cc=120

import argparse
import asyncio
import getpass
import os
import os.path
import types

from typing import Optional, Union

import ace.logging

from ace.constants import ACE_URI, ACE_API_KEY, ACE_PACKAGE_DIR, ACE_BASE_DIR, ACE_ADMIN_PASSWORD


def get_default_base_dir() -> str:
    """Returns whatever should be used for the default base directory."""
    return os.path.join(os.path.expanduser("~"), ".ace")


class ACEOperatingEnvironment:
    """Represents the environment in which ACE runs in."""

    def __init__(self, args=None, namespace=None):
        self.system = None
        parser, subparsers = self.initialize_argparse()
        self.args, remaining_arguments = parser.parse_known_args(args, namespace)
        ace.logging.initialize_logging(logging_config_path=self.args.logging_config_path)

        # initialize ACE packages
        from ace.packages.manager import ACEPackageManager

        self.package_manager = ACEPackageManager()
        self.package_manager.load_packages(package_dir=self.get_package_dir())
        self.package_manager.load_cli_commands(parser, subparsers)

        # parse again to get the full set of options from loaded packages
        self.args = parser.parse_args(args=remaining_arguments, namespace=self.args)

    def initialize_argparse(self):
        """Parses the arguments passed at startup."""

        parser = argparse.ArgumentParser(description="Analysis Correlation Engine", exit_on_error=False)
        subparsers = parser.add_subparsers(dest="cmd")

        parser.add_argument("-b", "--base-dir", help="Base directory for local ace storage. Defaults to ~/.ace")
        parser.add_argument("-u", "--uri", help="Target core URI. Defaults to ACE_URI environment variable.")
        parser.add_argument("-k", "--api-key", help="API key. Defaults to ACE_API_KEY environment variable.")
        parser.add_argument("-L", "--logging-config-path", default=None, help="Path to the logging configuration file.")
        parser.add_argument(
            "-V", "--disable-ssl-verification", default=False, action="store_true", help="Disable SSL verification."
        )
        parser.add_argument(
            "--package-dir",
            default=None,
            help="Path to the directory that contains installed ACE packages. Defaults to ~/.ace/packages",
        )

        import ace.cli.arguments
        import ace.packages.cli

        ace.cli.arguments.initialize_argparse(parser, subparsers)
        ace.packages.cli.initialize(parser, subparsers)
        return parser, subparsers

    async def execute(self):
        """Executes from the command line."""
        result = self.args.func(self.args)
        # this allows cli commands to optionally be defined async
        if isinstance(result, types.CoroutineType):
            return await result

        return result

    def get_uri(self) -> Union[str, None]:
        if self.args.uri:
            return self.args.uri

        if ACE_URI in os.environ:
            return os.environ[ACE_URI]

        return None

    def get_api_key(self) -> Union[str, None]:
        if self.args.api_key:
            return self.args.api_key

        if ACE_API_KEY in os.environ:
            return os.environ[ACE_API_KEY]

        return None

    def get_base_dir(self) -> str:
        """Returns the directory to use for ACE runtime operations. Defaults to ~/.ace"""
        if self.args.base_dir:
            return self.args.base_dir

        if ACE_BASE_DIR in os.environ:
            return os.environ[ACE_BASE_DIR]

        return get_default_base_dir()

    def get_package_dir(self) -> str:
        """Returns the directory that contains ACE packages. Defaults to ACE_BASE_DIR/packages"""
        if self.args.package_dir:
            return self.args.package_dir

        if ACE_PACKAGE_DIR in os.environ:
            return os.environ[ACE_PACKAGE_DIR]

        return os.path.join(self.get_base_dir(), "packages")

    def get_package_manager(self) -> "ACEPackageManager":
        return self.package_manager

    async def initialize_system_reference(self):
        """Initializes the reference to whatever system should be used based on
        environment variables and command line options."""
        from ace.crypto import EncryptionSettings
        from ace.cli.system import CommandLineSystem
        from ace.system.remote import RemoteACESystem

        # if a uri and api key are available then we want to use a remote system
        if self.get_uri() and self.get_api_key():
            is_local = False

            # keyword arguments to be passed to httpx.AsyncClient constructor
            client_kwargs = {}
            if self.args.disable_ssl_verification:
                client_kwargs["verify"] = False

            system = RemoteACESystem(self.get_uri(), self.get_api_key(), client_kwargs=client_kwargs)
        else:
            system = CommandLineSystem()

            # encryption settings are optional for local command line work
            encryption_settings = EncryptionSettings()
            encryption_settings.load_from_env()
            if encryption_settings.has_settings():
                encryption_settings.load_aes_key(self.get_admin_password())

        await system.initialize()
        self.set_system(system)

    async def get_system(self) -> "ACESystem":
        """Returns the current system reference."""
        return self.system

    def set_system(self, system: "ACESystem"):
        self.system = system

    def get_admin_password(self) -> str:
        """Returns the ACE admin password which is used to encrypt/decrypt data.
        If the environment variable ACE_ADMIN_PASSWORD is set then that value is used.
        Otherwise the value is prompted for."""
        if ACE_ADMIN_PASSWORD in os.environ:
            return os.environ[ACE_ADMIN_PASSWORD]

        return getpass.getpass(prompt="Enter admin password:")


# global operating environment
ACE_ENV: ACEOperatingEnvironment = None


def register_global_env(env: ACEOperatingEnvironment):
    """Registers the given environment as the global environment.
    This environment object is then returned by calls to get_env()."""
    global ACE_ENV
    ACE_ENV = env
    return env


def get_env() -> ACEOperatingEnvironment:
    """Returns the ACEOperatingEnvironment registered by the call to register_global_env."""
    return ACE_ENV


#
# shortcut versions of these functions that use the global environment
def get_uri() -> Union[str, None]:
    return get_env().get_uri()


def get_api_key() -> Union[str, None]:
    return get_env().get_api_key()


def get_base_dir() -> str:
    return get_env().get_base_dir()


def get_package_dir() -> str:
    return get_env().get_package_dir()


def get_package_manager() -> "ACEPackageManager":
    return get_env().get_package_manager()


async def get_system() -> "ACESystem":
    return await get_env().get_system()
