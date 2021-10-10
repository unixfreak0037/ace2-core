import uvicorn


def start_debug(args) -> bool:
    uvicorn.run(
        "ace.system.distributed:app",
        reload=True,
        host=args.address,
        port=args.port,
        log_level="debug",
        ssl_certfile=args.ssl_cert,
        ssl_keyfile=args.ssl_key,
    )
    return True


def initialize_argparse(parser, subparsers):
    debug_parser = subparsers.add_parser("debug", help="Starts a local ace system allowing debug.")
    debug_parser.add_argument("-a", "--address", default="127.0.0.1", help="Address to bind to. Defaults to 127.0.0.1")
    debug_parser.add_argument("-p", "--port", default=8443, type=int, help="Port to bind to. Defaults to 8443")
    debug_parser.add_argument(
        "--ssl-cert", default="etc/ssl/ace.cert.pem", help="SSL certificate to use. Defaults to etc/ssl/ace.cert.pem"
    )
    debug_parser.add_argument(
        "--ssl-key", default="etc/ssl/ace.key.pem", help="SSL key to use. Defaults to etc/ssl/ace.key.pem"
    )
    debug_parser.set_defaults(func=start_debug)
