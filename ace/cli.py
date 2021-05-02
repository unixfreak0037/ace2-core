# vim: ts=4:sw=4:et:cc=120

#
# command line interface
#

import argparse
import tempfile
import os.path


parser = argparse.ArgumentParser(description="Analysis Correlation Engine")
subparsers = parser.add_subparsers(dest="cmd")
args = None

parser.add_argument("-u", "--uri", help="Target core URI. Defaults to ACE_URI environment variable.")
parser.add_argument("-k", "--api-key", help="Core API key. Defaults to ACE_API_KEY environment variable.")
parser.add_argument("--package-dir", help="Directory that contains the definitions of installed ACE packages.")
parser.add_argument("-L", "--logging-config-path", default=None, help="Path to the logging configuration file.")


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


def recurse_analysis(analysis, level=0, current_tree=[]):
    """Used to generate a textual display of the analysis results."""
    if not analysis:
        return

    if analysis in current_tree:
        return

    current_tree.append(analysis)

    if level > 0 and len(analysis.observables) == 0 and len(analysis.tags) == 0 and analysis.summary is None:
        return

    analysis_display = analysis.root.description
    if analysis.type:
        analysis_display = f"{analysis.type.name}"
        if analysis.summary:
            analysis_display += f": {analysis.summary}"

    display = "{}{}{}".format(
        "\t" * level, "<" + "!" * len(analysis.detections) + "> " if analysis.detections else "", analysis_display
    )
    if analysis.tags:
        display += " [ {} ] ".format(", ".join([x.name for x in analysis.tags]))

    print(display)

    for observable in analysis.observables:
        display = "{} * {}{}:{}".format(
            "\t" * level,
            "<" + "!" * len(observable.detections) + "> " if observable.detections else "",
            observable.type,
            observable.value,
        )
        if observable.time is not None:
            display += " @ {0}".format(observable.time)
        if observable.directives:
            display += " {{ {} }} ".format(", ".join([x for x in observable.directives]))
        if observable.tags:
            display += " [ {} ] ".format(", ".join([x.name for x in observable.tags]))
        print(display)

        for observable_analysis in observable.all_analysis:
            recurse_analysis(observable_analysis, level + 1, current_tree)


def display_analysis(root):
    recurse_analysis(root)

    tags = set(root.all_tags)
    if tags:
        print("{} TAGS".format(len(tags)))
        for tag in tags:
            print("* {}".format(tag))

    detections = root.all_detection_points
    if detections:
        print("{} DETECTIONS FOUND (marked with <!> above)".format(len(detections)))
        for detection in detections:
            print("* {}".format(detection))
