# Work Queues

A **work queue** is a queue created for each [analysis module type](analysis_module_type.md) registered with the system. These queues are filled with [analysis requests](analysis_requests.md) that are generated when other analysis requests are processed by the system.

Each analysis module type gets exactly *one* work queue associated to it. Work is pulled from this work queue in a manner such that each item pulled can only be pulled once.