from ace.env import get_system


async def create_api_key(args):
    system = await get_system()
    api_key = await system.create_api_key(args.name, description=args.description, is_admin=args.is_admin)
    print(api_key.api_key)
    return True


async def list_api_keys(args):
    system = await get_system()
    for api_key in await system.get_api_keys():
        print(api_key)

    return True


async def delete_api_key(args):
    system = await get_system()
    if await system.delete_api_key(args.name):
        print("key deleted")
    else:
        print("key not found")

    return True


def initialize_argparse(parser, subparsers):
    api_key_parser = subparsers.add_parser("api-key", help="Manage api keys.")
    api_key_sp = api_key_parser.add_subparsers(dest="api_key_cmd")

    create_api_key_parser = api_key_sp.add_parser("create", help="Create a new api key.")
    create_api_key_parser.add_argument("name", help="The name of the api key. Must be unique.")
    create_api_key_parser.add_argument("--description", help="Optional description of the account.")
    create_api_key_parser.add_argument(
        "--is-admin", action="store_true", default=False, help="Creates an administrative key."
    )

    create_api_key_parser.set_defaults(func=create_api_key)

    list_api_key_parser = api_key_sp.add_parser("list", help="List all API keys.")
    list_api_key_parser.set_defaults(func=list_api_keys)

    delete_api_key_parser = api_key_sp.add_parser("delete", help="Delete an API key.")
    delete_api_key_parser.add_argument("name", help="The name of the api key to delete.")
    delete_api_key_parser.set_defaults(func=delete_api_key)
