# Analysis Module Type

An `ace.analysis.AnalysisModuleType` represents a type of analysis module type that can be registered and used to analyze observables. The specification of the type dictates things like 

- what observables it is interested in analyzing.
- what other analysis modules it depends on.
- how long to cache analysis results.
- what version it is currently at.

ACE supports any number of instances of a given analysis module type running concurrently.