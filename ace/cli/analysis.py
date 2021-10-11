import sys
import tempfile

# from ace.cli import CommandLineSystem, display_analysis
from ace.analysis import RootAnalysis
from ace.env import get_uri, get_api_key
from ace.logging import get_logger
from ace.module.manager import AnalysisModuleManager, CONCURRENCY_MODE_PROCESS, CONCURRENCY_MODE_THREADED
from ace.system.remote import RemoteACESystem
from ace.time import event_time_format_tz


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
        display += " [ {} ] ".format(", ".join(analysis.tags))

    print(display)

    for observable in analysis.observables:
        display = "{} * {}{}:{}".format(
            "\t" * level,
            "<" + "!" * len(observable.detections) + "> " if observable.detections else "",
            observable.type,
            observable.value,
        )
        if observable.time is not None:
            display += f" @ {observable.time.strftime(event_time_format_tz)}"
        if observable.directives:
            display += " {{ {} }} ".format(", ".join([x for x in observable.directives]))
        if observable.tags:
            display += " [ {} ] ".format(", ".join(observable.tags))
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


def initialize_argparse(parser, subparsers):
    analyze_parser = subparsers.add_parser("analyze", help="Analyze given observables.")
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
