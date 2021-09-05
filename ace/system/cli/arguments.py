import ace.system.cli.system
import ace.system.cli.analysis


def initialize_argparse(parser, subparsers):
    ace.system.cli.system.initialize_argparse(parser, subparsers)
    ace.system.cli.analysis.initialize_argparse(parser, subparsers)
