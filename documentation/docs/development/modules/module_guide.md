# Analysis Module Development Guide (Python)

The ACE core library provides base classes and utilities for developing analysis modules. They are provided as a means to accelerate development. You do not need to use them (see [this guide instead.]())

## Overview

You create new analysis modules by

- defining a new *type* of analysis
- creating the Python code that implements the analysis
- registering the new type with an executing core
- starting an *analysis module manager* with the new module loaded

## Analysis Module Type

An analysis module **type** describes all the properties of the analysis module such as

- what observables it wants to analyze
- what additional information is required before the module will consider analyzing it

In the core library the type is represented by the `ace.analysis.AnalysisModuleType` class.

## Analysis Module

The module that implements the analysis logic is represented by the `ace.module.AnalysisModule` class. Every instance of `AnalysisModule` has an associated `AnalysisModuleType`.

Note that the **type** is separate from the implementation.

A simple example of an analysis module that does nothing is as follows.

```python
class MyAnalysisModule(AnalysisModule):
    type = AnalysisModuleType(name="my_analysis_module", description="My Analysis Module")

    def execute_analysis(self, root, observable, analysis):
        pass
```

## Loading Additional Resources

Override and use the `load` function to load additional resources such as signatures and resource files.

```python
class MyAnalysisModule(AnalysisModule):
    type = AnalysisModuleType(name="my_analysis_module", description="My Analysis Module")

    def execute_analysis(self, root, observable, analysis):
        pass

    def load(self):
        # load signature files
        # open files
        # open network connections
```

## Async vs Sync

The ACE core library supports analysis modules written to taken advantage of the `asyncio` library.

If you prepend `async` to `execute_analysis` then the module will be considered `async`. Otherwise the module is considered `sync`.

Modules that are `sync` are executed on their own process. Modules that are `async` are executed as part of the `asyncio` event loop.

```python
# define an analysis module that uses asyncio
class MyAsyncAnalysisModule(AnalysisModule):
    type = AnalysisModuleType("async_module", "")

    async def execute_analysis(self, root, observable, analysis):
        # do async stuff

```

## Analysis

You are expected to analyze the observable passed into the `execute_analysis` function, and store the results in the `analysis` object.

The details of the analysis are stored in the `details` property of the `analysis` object. This value must be a `dict` that can be translated into JSON using Python's standard `json` library.

```python
def execute_analysis(self, root, observable, analysis):
    # details have no schema
    analysis.details = { "results": "my results here" }
```

You can also add an additional [observables]() you find.

```python
def execute_analysis(self, root, observable, analysis):
    # details have no schema
    analysis.details = { "results": "my results here" }
    # add an ip address as an observable
    analysis.add_observable("ipv4", "1.2.3.4")
```

You can [do a lot of other things with observables.]()