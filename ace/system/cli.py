# vim: ts=4:sw=4:et:cc=120

from ace.cli import get_cli_sp
from ace.env import get_uri, get_api_key
from ace.logging import get_logger
from ace.module.manager import AnalysisModuleManager, CONCURRENCY_MODE_PROCESS, CONCURRENCY_MODE_THREADED
from ace.system.database import DatabaseACESystem
from ace.system.remote import RemoteACESystem


async def analyze(args):

    if len(args.targets) % 2 != 0:
        get_logger().error("odd number of arguments (you need pairs of type and value)")
        return False

    targets = args.targets

    uri = get_uri()
    api_key = get_api_key()

    if uri and api_key:
        system = RemoteACESystem(uri, api_key)
    else:
        system = DatabaseACESystem(db_url="sqlite+aiosqlite://")

    await system.initialize()

    # TODO move this to the system
    if isinstance(system, DatabaseACESystem):
        from ace.system.database.schema import Base

        Base.metadata.bind = system.engine
        async with system.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    manager = AnalysisModuleManager(system, type(system), (system.db_url,), concurrency_mode=CONCURRENCY_MODE_PROCESS)
    # TODO load all the analysis modules we know about
    if not manager.analysis_modules:
        get_logger().error("no modules loaded")
        return False

    root = system.new_root()

    index = 0
    while index < len(args.targets):
        o_type = args.targets[index]
        o_value = args.targets[index + 1]

        # TODO if you add a file then add_observable should call add_file
        root.add_observable(o_type, o_value)

    await root.submit()
    await manager.run_once()

    root = await system.get_root_analysis(root)
    root.stdout()  # TODO
    return True


analyze_parser = get_cli_sp().add_parser("analyze", help="Analyze given observables.")
analyze_parser.add_argument("targets", nargs="*", help="One or more pairs of indicator types and values.")
analyze_parser.set_defaults(func=analyze)
