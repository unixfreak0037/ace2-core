# Core System

ACE is composed of subsystem component interfaces. Each interface allows implementation of a particular part of the system. An implementation of these interfaces would create a complete ACE core system.

## System Interfaces

The following interfaces make up the entirety of the ACE system.

- Alerting
- Analysis Tracking
- Caching
- Configuration
- Events
- Locking
- Analysis Module Tracking
- Observables
- Analysis Request Tracking
- Storage
- Work Queues

## Process Workflow Overview

The following is a basic high level overview of the fundamental logic of the analysis system.

1. Register one or more analysis modules.
2. Submit a new analysis request.
3. New analysis requests are added to the work queues based on the content of the submission.
4. Analysis modules pull requests from the work queues.
5. Analysis modules post results of the analysis.
6. New analysis requests are added to the work queues based on the content of the posted results.
7. Process continues until work queues are emptied.
