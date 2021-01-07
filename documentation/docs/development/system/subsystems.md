# Core Subsystems

## Implementations

The core library contains some default implementations of the subsystems for various usages.

### Threaded

The threaded subsystem interfaces defined in `ace.system.threaded` are simple implementations that:

- assume the entire system runs in a single process under multiple threads
- tracks all data in in-memory data structures

It is used for unit testing and one-off command line analysis.

### Database

The database subsystem interfaces defined in `ace.system.database` are implementations that use SQLalchemy to track data. The schema of the database tables are defined in `ace.database.schema`.

### Distributed

The distributed subsystem interfaces defined in `ace.system.distributed` are implementations that use FastAPI to expose the interfaces to external systems.

The distributed subsystem can be used to implement a highly scalable ACE core system.

## Core Subsystem Composition

The ACE core can be composed of any combination of subsystem implementations. They can be mixed in whatever combination is required.

This is possible because each subsystem has no dependency on another except through the core system API.
