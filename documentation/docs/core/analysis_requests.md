# Analysis Requests

There are three types of analysis requests.

## Root Analysis Requests

A **root analysis request** is one that contains only a [root analysis](../design/root_analysis.md) object. If the root analysis object does not exist, it is added to the system and [tracked](analysis_tracking.md).

If the root analysis already exists, it is replaced by a copy of a new one that merges the new analysis into the old one.

## Observable Analysis Request

An **observable analysis request** is one that contains both a [root analysis](../design/root_analysis.md) object and an [observable](../design/observable.md) object, as well as a copy of the [analysis module type](analysis_module_type.md) that is supposed to analyze it.

These requests are added to the work queues of their respective analysis module types.

References to observable analysis requests are also tracked inside the observables themselves.

## Observable Analysis Result

[Analysis modules](../design/analysis_module.md) record analysis results inside of the requests they receive. In other words, the analysis results are appended to the original request. These **observable analysis results** are then resubmitted back to the core system for processing. The observable analysis result is an analysis *request* when it's resubmitted back to the core system for processing.