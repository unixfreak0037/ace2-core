import ace.cli.analysis
import ace.cli.auth
import ace.cli.debug
import ace.cli.system


def initialize_argparse(parser, subparsers):
    ace.cli.debug.initialize_argparse(parser, subparsers)
    ace.cli.system.initialize_argparse(parser, subparsers)
    ace.cli.analysis.initialize_argparse(parser, subparsers)
    ace.cli.auth.initialize_argparse(parser, subparsers)
