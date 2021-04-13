# Core Subsystems

## Implementations

The core library contains some default implementations of the subsystems for various usages.

### Threaded

The threaded system defined in `ace.system.threaded` is a simple implementation that:

- assumes the entire system runs in a single process under multiple threads
- tracks all data in in-memory data structures

It is used for unit testing and one-off command line analysis.

### Process

Defined in `ace.system.process` and similar to the threaded system but uses actual system processes instead. Used for command line analysis that needs to use the full CPU capacity of the system.

### Database

Defined in `ace.system.database`. Uses SQLalchemy to track data. The schema of the database tables are defined in `ace.database.schema`.

Used by both the cli and the distributed system.

### Distributed

A distributed system interface defined in `ace.system.distributed` that uses FastAPI to expose specific core API functions to external systems.

The distributed subsystem can be used to implement a highly scalable ACE core system.

### Remote

A *partial* system that uses a **distributed** system running somewhere else. Only the functions exposed by the distributed system are implemented in this system.

This system is used by the [Analysis Module Manager]() to communicate with a remote core system.

## Core Subsystem Composition

The ACE core can be composed of any combination of subsystem implementations. They can be mixed in whatever combination is required.

Each subsystem has no dependency on another except through the core system API.
