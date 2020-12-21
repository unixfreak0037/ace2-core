# Analysis

An **analysis** is the output of the analysis of an [observable](observable.md). It consists of

- zero or more observables.
- a free form JSON formatted analysis output.
- zero or more [tags](tags.md).
- zero or more [detection points](detection_points.md).

The relationship between analysis and observable is always parent-child.

## Analysis Details

The **details** of the analysis is simply free-form JSON-compatible data. This can be any value. The interpretation of this value is up to the python classes that implement the [analysis modules](analysis_module.md) and analysis objects.

These details are stored separately from the JSON of the main [root analysis](root_analysis.md) object. They are loaded as needed. A brief summary of the details are stored instead.
