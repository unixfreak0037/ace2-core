# vim: ts=4:sw=4:et:cc=120

from ace.cli import get_cli, get_cli_sp, display_analysis
from ace.packages import install_package

get_cli().add_argument(
    "--package-dir",
    default=None,
    help="Path to the directory that contains installed ACE packages. Defaults to ~/.ace/packages",
)

package_parser = get_cli_sp().add_parser("package", help="ACE package management.")
package_sp = package_parser.add_subparsers(dest="package_cmd")


async def install(args):
    install_package(args.package)


install_parser = package_sp.add_parser("install", help="Installs an ACE package.")
install_parser.add_argument("package", help="The ACE package to install.")
install_parser.set_defaults(func=install)
