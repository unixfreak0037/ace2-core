# vim: ts=4:sw=4:et:cc=120

from ace.cli import get_cli_sp
from ace.packages import get_package_manager
from ace.service.manager import ACEServiceDB, ACEServiceManager

# TODO use texttable

service_parser = get_cli_sp().add_parser("service", help="ACE service management.")
service_sp = service_parser.add_subparsers(dest="service_cmd")


def list_services(args):
    if args.verbose:
        print("{:<20}Description".format("Service Name"))

    for service in get_package_manager().services:
        if args.verbose:
            if service.description:
                print(f"{service.name: <20}{service.description}")
            else:
                print(f"{service.name: <20}")
        else:
            print(service.name)


list_parser = service_sp.add_parser("list", help="Lists all available ACE services.")
list_parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    default=False,
    help="Include additional service information and header values.",
)
list_parser.set_defaults(func=list_services)


def show_service_status(args):
    service_db = ACEServiceDB()
    for service_info in service_db.get_all_service_info():
        print(f"{service_info.name}\t{service_info.status}\t{service_info.pid}")


show_status_parser = service_sp.add_parser("status", help="Display the current status of ACE services.")
show_status_parser.set_defaults(func=show_service_status)


def start_services(args):
    manager = ACEServiceManager()
    for service_type in get_package_manager().services:
        if not args.services or service_type.name in args.services:
            service = service_type()
            manager.schedule_service(service)

    manager.start()


start_services_parser = service_sp.add_parser(
    "start", help="Starts one or more services. Exits when all services have shut down."
)
start_services_parser.add_argument(
    "services",
    nargs="*",
    help="""One or more names of services to start. Use the list command to get the list of available services.
    If no services are specified then all enabled services are started.""",
)
start_services_parser.set_defaults(func=start_services)
