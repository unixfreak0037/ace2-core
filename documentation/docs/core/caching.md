# Caching

The results of analysis work are returned as [analysis requests](analysis_request_tracking). If the [analysis module type](analysis_module_type.md) supports **caching** then these analysis results are tracked by `ace.system.caching.CacheInterface`.

The [analysis result](analysis_requests.md) contains a copy of the [root analysis](../design/root_analysis.md) and the [observable](../design/observable.md) as they existed *before* the analysis, as well as the modified version as they existed *after* the analysis.

When an analysis is requested for an observable that has a cached result, the *difference* between the before and after copies of the root and observables are applied.

Caching uses a **cache key** to index the cached analysis results. The key is generated from a combination of:

- the type of the observable
- the value of the observable
- the time of the observable (if available)
- the name of the analysis module type
- the version of the analysis module type
- optionally, any additional cache keys specified by the analysis module type

If the cache key changes then the lookup changes.

Cache results can be set to expire after a period of time as specified by the analysis module type.