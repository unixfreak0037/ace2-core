# vim: ts=4:sw=4:et:cc=120

from ace.cli import get_cli, get_cli_sp, display_analysis
from ace.env import get_package_dir
from ace.packages import get_package_manager

get_cli().add_argument(
    "--package-dir",
    default=None,
    help="Path to the directory that contains installed ACE packages. Defaults to ~/.ace/packages",
)

package_parser = get_cli_sp().add_parser("package", help="ACE package management.")
package_sp = package_parser.add_subparsers(dest="package_cmd")


async def list_packages(args):
    packages = get_package_manager().load_packages()
    if not packages:
        print(f"no packages installed in {get_package_dir()}")
        return

    for package in packages:
        if args.verbose:
            print(
                f"""Name: {package.name}
Version: {package.version}
Source: {package.source}
Description:
    {package.description}"""
            )
            # TODO print everything else too
        else:
            print(f"{package.name} v{package.version}")


list_parser = package_sp.add_parser("list", help="Lists all installed ACE packages.")
list_parser.add_argument(
    "-v", "--verbose", action="store_true", default=False, help="Show detailed package information."
)
list_parser.set_defaults(func=list_packages)
