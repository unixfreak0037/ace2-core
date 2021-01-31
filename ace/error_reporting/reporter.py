# vim: ts=4:sw=4:et:cc=120
#

import sys

from typing import Optional

from ace.error_reporting.formatter import ExceptionFormatter


def format_error_report(reported_exception: Optional[Exception] = None) -> str:
    """Formats and returns an error report using the provided exception, or the
    most recent exception if None was provided."""

    if reported_exception is None:
        exc_type, reported_exception, tb = sys.exc_info()
    else:
        exc_type, reported_exception, tb = (
            type(reported_exception),
            reported_exception,
            reported_exception.__traceback__,
        )

    formatter = ExceptionFormatter()
    stack_trace, final_source = formatter.format_traceback(tb)

    return f"""EXCEPTION
{reported_exception}

STACK TRACE
{stack_trace}

EXCEPTION SOURCE
{final_source}
"""
