import base64
import getpass
import os


from ace.constants import ACE_ADMIN_PASSWORD
from ace.crypto import (
    initialize_encryption_settings,
    ENV_CRYPTO_VERIFICATION_KEY,
    ENV_CRYPTO_SALT,
    ENV_CRYPTO_SALT_SIZE,
    ENV_CRYPTO_ITERATIONS,
    ENV_CRYPTO_ENCRYPTED_KEY,
)
from ace.logging import get_logger
from ace.system.database import DatabaseACESystem
from ace.system.database.schema import Base
from ace.system.default import DefaultACESystem
from ace.system.threaded import ThreadedACESystem


class CommandLineSystem(DatabaseACESystem, ThreadedACESystem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_url = "sqlite+aiosqlite://"


async def initialize(args) -> bool:
    """Initializes the ACE system.
    - creates the database if one has not already been created
    - initializes encryption settings
    - creates the initial admin api key
    Returns True on success, False on failure."""
    # initialize the default system
    system = DefaultACESystem()
    await system.initialize()

    encryption_password = None
    if ACE_ADMIN_PASSWORD in os.environ:
        encryption_password = os.environ[ACE_ADMIN_PASSWORD]

    if not encryption_password:
        encryption_password = getpass.getpass("Enter the ACE administration password:")

    if not encryption_password:
        get_logger().error(f"missing {ACE_ADMIN_PASSWORD}")
        return False

    get_logger().info("initializing database")
    Base.metadata.bind = system.engine
    async with system.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # initialize encryption settings
    get_logger().info("initializing encryption settings")
    system.encryption_settings = await initialize_encryption_settings(encryption_password)

    verification_key_encoded = base64.b64encode(system.encryption_settings.verification_key).decode()
    salt_encoded = base64.b64encode(system.encryption_settings.salt).decode()
    salt_size_encoded = str(system.encryption_settings.salt_size)
    iterations_encoded = str(system.encryption_settings.iterations)
    encrypted_key_encoded = base64.b64encode(system.encryption_settings.encrypted_key).decode()

    api_key = await system.create_api_key("root", "admin", is_admin=True)

    print("# START EXPORT")
    print(f"export {ENV_CRYPTO_VERIFICATION_KEY}={verification_key_encoded}")
    print(f"export {ENV_CRYPTO_SALT}={salt_encoded}")
    print(f"export {ENV_CRYPTO_SALT_SIZE}={salt_size_encoded}")
    print(f"export {ENV_CRYPTO_ITERATIONS}={iterations_encoded}")
    print(f"export {ENV_CRYPTO_ENCRYPTED_KEY}={encrypted_key_encoded}")
    print(f"export ACE_API_KEY={api_key}")
    print("# STOP EXPORT")

    return True


def initialize_argparse(parser, subparsers):
    init_parser = subparsers.add_parser("initialize", help="Initialize a new ACE system.")
    init_parser.set_defaults(func=initialize)
