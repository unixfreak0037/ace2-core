# vim: ts=4:sw=4:et:cc=120

#
# command line interface
#

import argparse

parser = argparse.ArgumentParser(description="Analysis Correlation Engine")
subparsers = parser.add_subparsers(dest="cmd")
args = None

parser.add_argument("-u", "--uri", help="Target core URI. Defaults to ACE_URI environment variable.")
parser.add_argument("-k", "--api-key", help="Core API key. Defaults to ACE_API_KEY environment variable.")


def get_cli():
    return parser


def get_cli_sp():
    return subparsers


def parse_args():
    global args
    args = parser.parse_args()
    return args


def get_args():
    return args
