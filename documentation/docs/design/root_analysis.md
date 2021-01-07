# Root Analysis

The [analysis](analysis.md) --> [observable](observable.md) --> [analysis](analysis.md) relationship forms a hierarchical tree with a special analysis object called the **root analysis** as the starting point of the tree.

A root analysis is a special type of [analysis](analysis.md) object that contains additional information about the analysis as a whole, such as, what generated it, description information, instructions for analysts, etc...

A root analysis can become an [alert](alerts.md) if one or more [detection points](detection_points.md) are added during the course of analysis.
