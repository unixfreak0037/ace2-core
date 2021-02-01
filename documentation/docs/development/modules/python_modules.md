# Analysis Modules (Python)

Analysis modules extend the `ace.module.base.AnalysisModule` class. The only function that needs to be implemented is the `execute_analysis` function.

```python
def execute_analysis(root, observable, analysis)
```

Execute analysis takes three parameters:

- `root` - the [root]() analysis object.
- `observable` - the observable to be analyzed
- `analysis` - prepared analysis object to store the results of the analysis into

# Synchronous vs Asynchronous

Analysis modules can be either *synchronous* or *asyncronous*. By default modules are synchronous. To define an analysis module as asynchronous, simply add the `async` modified to the function definition.

```python
# defines a module as async
async def execute_analysis(root, observable, analysis)
```

Async modules are executed as part of Python's asyncio event loop.

Sync modules are executed *on their own child process*.

Async modules are appropriate for the following types of I/O bound analysis:

- API calls
- external process execution
- generic networking
- fast analysis

Sync modules are approproate for CPU intensive types of analysis.