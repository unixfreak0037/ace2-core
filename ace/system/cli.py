# vim: ts=4:sw=4:et:cc=120

import base64
import getpass
import os
import sys
import tempfile

from ace.cli import get_cli_sp, display_analysis
from ace.constants import ACE_ADMIN_PASSWORD
from ace.crypto import (
    initialize_encryption_settings,
    ENV_CRYPTO_VERIFICATION_KEY,
    ENV_CRYPTO_SALT,
    ENV_CRYPTO_SALT_SIZE,
    ENV_CRYPTO_ITERATIONS,
    ENV_CRYPTO_ENCRYPTED_KEY,
)
from ace.env import get_uri, get_api_key
from ace.logging import logger
from ace.module.manager import AnalysisModuleManager, CONCURRENCY_MODE_PROCESS, CONCURRENCY_MODE_THREADED
from ace.system.database import DatabaseACESystem
from ace.system.database.schema import Base
from ace.system.default import DefaultACESystem
from ace.system.threaded import ThreadedACESystem
from ace.system.remote import RemoteACESystem


class CommandLineSystem(DatabaseACESystem, ThreadedACESystem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_url = db_url = "sqlite+aiosqlite://"


async def analyze(args):

    if len(args.targets) % 2 != 0:
        get_logger().error("odd number of arguments (you need pairs of type and value)")
        return False

    targets = args.targets

    # did we specify targets from stdin?
    if args.from_stdin:
        for o_value in sys.stdin:
            # the type of observables coming in on stdin is also specified on the command line
            targets.append(args.stdin_type)
            targets.append(o_value.strip())

    is_local = True
    uri = get_uri()
    api_key = get_api_key()

    if uri and api_key:
        is_local = False
        system = RemoteACESystem(uri, api_key)
    else:
        system = CommandLineSystem()
        system.storage_root = tempfile.mkdtemp()

    await system.initialize()

    # TODO move this to the system
    if is_local:
        await system.create_database()

    manager = AnalysisModuleManager(system, type(system), (system.db_url,), concurrency_mode=CONCURRENCY_MODE_PROCESS)
    manager.load_modules()

    if not manager.analysis_modules:
        get_logger().error("no modules loaded")
        return False

    if is_local:
        for module in manager.analysis_modules:
            await system.register_analysis_module_type(module.type)

    root = system.new_root()

    if args.analysis_mode:
        root.analysis_mode = args.analysis_mode

    index = 0
    while index < len(args.targets):
        o_type = args.targets[index]
        o_value = args.targets[index + 1]

        # TODO if you add a file then add_observable should call add_file
        if o_type == "file":
            await root.add_file(o_value)
        else:
            root.add_observable(o_type, o_value)

        index += 2

    await root.submit()
    await manager.run_once()

    root = await system.get_root_analysis(root)
    display_analysis(root)
    return True


analyze_parser = get_cli_sp().add_parser("analyze", help="Analyze given observables.")
# options on the RootAnalysis
analyze_parser.add_argument("-m", "--analysis-mode", help="Sets the analysis mode of the root.")
analyze_parser.add_argument(
    "--from-stdin",
    action="store_true",
    default=False,
    help="Read observables from standard input. Default observable type is file. Use --stdin-type to change the type.",
)
analyze_parser.add_argument(
    "--stdin-type",
    default="file",
    help="Specify the observable type when reading observables from stdin. Defaults to file.",
)
analyze_parser.add_argument("targets", nargs="*", help="One or more pairs of indicator types and values.")
analyze_parser.set_defaults(func=analyze)


async def initialize(args):
    # initialize the default system
    system = DefaultACESystem()
    await system.initialize()
    logger.info("creating database...")
    Base.metadata.bind = system.engine
    async with system.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    encryption_password = None
    if ACE_ADMIN_PASSWORD in os.environ:
        encryption_password = os.environ[ACE_ADMIN_PASSWORD]

    if not encryption_password:
        encryption_password = getpass.getpass("Enter the ACE administration password:")

    if not encryption_password:
        logging.error(f"missing {ACE_ADMIN_PASSWORD}")
        sys.exit(1)

    # initialize encryption settings
    system.encryption_settings = await initialize_encryption_settings(encryption_password)

    verification_key_encoded = base64.b64encode(system.encryption_settings.verification_key).decode()
    print(f'export {ENV_CRYPTO_VERIFICATION_KEY}="{verification_key_encoded}"')
    salt_encoded = base64.b64encode(system.encryption_settings.salt).decode()
    print(f'export {ENV_CRYPTO_SALT}="{salt_encoded}"')
    salt_size_encoded = str(system.encryption_settings.salt_size)
    print(f'export {ENV_CRYPTO_SALT_SIZE}="{salt_size_encoded}"')
    iterations_encoded = str(system.encryption_settings.iterations)
    print(f'export {ENV_CRYPTO_ITERATIONS}="{iterations_encoded}"')
    encrypted_key_encoded = base64.b64encode(system.encryption_settings.encrypted_key).decode()
    print(f'export {ENV_CRYPTO_ENCRYPTED_KEY}="{encrypted_key_encoded}"')

    # install root api key
    api_key = await system.create_api_key("root", "admin", is_admin=True)
    print(f'export ACE_API_KEY="{api_key}"')


init_parser = get_cli_sp().add_parser("initialize", help="Initialize a new ACE system.")
init_parser.set_defaults(func=initialize)
