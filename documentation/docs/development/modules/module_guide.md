# Analysis Module Development Guide (Python)

The ACE core library provides base classes and utilities for developing analysis modules. They are provided as a means to accelerate development. You do not need to use them (see [this guide instead.]())

## TL;DR

### Step 1: Define the Module Type

```python
from ace.analysis import AnalysisModuleType
amt = AnalysisModuleType(
    name="example_analysis",
    description="Example analysis module type."
)
```

### Step 2: Define the Analysis Module

```python
from ace.module.base import AnalysisModule
class ExampleAnalysisModule(AnalysisModule):
    type = amt
    def execute_analysis(self, root, observable, analysis):
        analysis.details = {"Hello": "World"}
        observable = analysis.add_observable("ipv4", "1.2.3.4")
        observable.add_detection_point("lol evil ip")
```

### Step 3: Register the Module Type

```python
from ace.api import get_api
get_api().register_analysis_module_type(amt)
```

### Step 4: Run an Analysis Module Manager

```python
from ace.module.manager import AnalysisModuleManager
manager = AnalysisModuleManager()
manager.add_module(ExampleAnalysisModule())
manager.run()
```

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
class ExampleAnalysisModule(AnalysisModule):
    type = AnalysisModuleType(
        name="example_analysis_module", 
        description="Example analysis module that does nothing.")

    def execute_analysis(self, root, observable, analysis):
        pass
```

## Loading Additional Resources

Override and use the `load` function to load additional resources such as signatures and resource files.

```python
class ExampleAnalysisModule(AnalysisModule):
    type = AnalysisModuleType(
        name="example_analysis_module", 
        description="Example analysis module that does nothing.")

    def execute_analysis(self, root, observable, analysis):
        pass

    def load(self):
        # load signature files
        # open files
        # open network connections
```

## Upgrading

Override the `upgrade` function to re-load any data needed to compute the analysis. This is useful for analysis modules that use external data such as signatures and rule sets.

```python
class ExampleAnalysisModule(AnalysisModule):
    type = AnalysisModuleType(
        name="example_analysis_module", 
        description="Example analysis module that does nothing.")

    def execute_analysis(self, root, observable, analysis):
        pass

    def upgrade(self):
        # (for example)
        self.rules = self.load_my_rule_set()
```

## Async vs Sync

The ACE core library supports analysis modules written to taken advantage of the `asyncio` library.

If you prepend `async` to `execute_analysis`, `upgrade` and `load` then the module will be considered `async`. Otherwise the module is considered `sync`.

Modules that are `sync` are executed on their own process. Modules that are `async` are executed as part of the `asyncio` event loop.

```python
# define an analysis module that uses asyncio
class ExampleAsyncAnalysisModule(AnalysisModule):
    type = AnalysisModuleType(
        name="async_module", 
        description="Example async analysis module."
    )

    async def execute_analysis(self, root, observable, analysis):
        # do async analysis

    async def upgrade(self):
        # do async upgrade

    async def load(self):
        # do async load

```

You can also use the `AsyncAnalysisModule` class which already has the function definitions set up correctly (meaning you don't have to override upgrade and load if you're not using them.)

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