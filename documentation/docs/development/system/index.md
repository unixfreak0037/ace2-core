# Core System

## Subsystem Composition

The core system is composed of subsystems that implement some required features of ACE. The full contract of the entire system is found [here](https://github.com/ace-ecosystem/ace2-core/blob/main/ace/system/__init__.py).

The core system is composed of [multiple interfaces](https://docs.python.org/3/tutorial/classes.html#multiple-inheritance) that make up an entire system. Thus, you can create a core that is made of the subsystems that provide the functionality you need for however you need to run the core.

For example, the threaded system implements a very simple in-memory threaded version of various subsystems suitable for unit testing.

## Core API

The core API is the set of function calls made available by all of the subsystem interfaces. These functions are decorated with the `@coreapi` decorator.
