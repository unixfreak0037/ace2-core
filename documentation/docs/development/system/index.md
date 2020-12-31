# Core System

## Global System Reference

The core system is composed of subsystems that implement some required feature of ace. The full contract of the entire system is found [here](https://github.com/ace-ecosystem/ace2-core/blob/main/ace/system/__init__.py).

A reference to the global instance of the core system can be obtained by calling `ace.system.get_system()`. The properties of this object are references to implementations of the subsystem interfaces.

For example

```python
from ace.system import get_system

# obtain a reference to the analysis tracking subsystem
get_system().analysis_tracking
```

## Core API

The core API is the set of function calls made available by all of the subsystem interfaces.

There are two sets of API functions: *interface* and *module*.

**The module API is the full ace core API**.

### Interface API Functions

Each subsystem interface defines what functions needs to be implemented. For example

```python
class AlertTrackingInterface(ACESystemInterface):
    """Tracks alerts as they are detected during the processing of analysis requests."""

    def track_alert(self, root: RootAnalysis) -> Any:
        raise NotImplementedError()

    def get_alert(self, id: str) -> Union[Any, None]:
        raise NotImplementedError()

```

To call the `track_alert` function using the interface API we would do the following

```python
get_system().alerting.track_alert(root)
```

In this code we

- obtain a reference to the core system with `get_system()`
- obtain a reference to the alert tracking subsystem with `.alerting`
- call the `track_alert` interface API function

### Module API Functions

The interface API functions are wrapped by functions defined at the module level. The functions provide additional functionality such as 

- error and type checking
- parameter casting
- logging

Outside of subsystem interface development, it is better to use the module API functions to interact with the core system.

For example `ace.system.analysis_tracking.AnalysisTrackingInterface` defines the `get_root_analysis` function which could be called like this

```python
root = get_system().analysis_tracking.get_root_analysis(uuid)
```

It is recommended to call the same function like this

```python
from ace.system.analysis_tracking import get_root_analysis
root = get_root_analysis(uuid)
```

There are module API functions that do not have corresponding interface API functions, but may be composed of them. For example, `ace.system.work_queue.get_next_analysis_request` has no corresponding interface API function, but is composed of calls to multiple interface API functions.

## Summary

Ace core is composed of subsystems referenced by `get_system()`. Each subsystem defines interface API functions, which are wrapped by module API functions. The entire ace core API is the full set of module API functions.
