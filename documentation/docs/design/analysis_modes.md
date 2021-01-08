# Analysis Modes

**Analysis modes** provide a way to logically group together different analysis modules and have them execute as a group. The analysis mode is a property of a [root analysis](root_analysis.md) object that determines what set of [analysis modules](analysis_module.md) (might) execute on observables in the object. Analysis modes are created by having [analysis module types](../core/analysis_module_type.md) specify them in their list of constraints and requirements.

Any analysis module can change the analysis mode of a root analysis object, which will in turn change what analysis modules continue to be executed against it.