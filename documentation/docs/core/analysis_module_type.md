# Analysis Module Type

An **analysis module type** represents a *type* of analysis module that can be registered and used to analyze [observables](../design/observable.md). The specification of the type determines 

- what observables it is interested in analyzing.
- what other analysis modules it depends on.
- how long to cache analysis results.
- what version it is currently at.

ACE supports any number of instances of a given analysis module type running concurrently.