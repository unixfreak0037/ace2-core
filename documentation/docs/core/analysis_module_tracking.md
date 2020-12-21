# Analysis Module Tracking

Analysis modules are tracked as [analysis module types](analysis_module_type.md) through the interface `ace.system.analysis_module_tracking.AnalysisModuleTrackingInterface`. 

Analysis modules start by registering with the system. Multiple instances of the same analysis module can register as long as the version of the module remains the same. The keeps track of what analysis modules have been registered and have not expired or been invalidated.

Each analysis module type is assigned a work queue. Any work created that the analysis module supports is assigned to the work queue. Any instance of the analysis module can pick up the work from the queue.

When an analysis module requests work, it also submits its current version data so that it can be checked against the registered analysis module.

## Versions

Every analysis module type has a version as defined by a number of properties. When an analysis module registers a new version, the new type replaces the old type. Any attempts acquire work with the old version are denied.