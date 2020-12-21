# ACE2 - Core System

Work in progress as I port over to this new 2.0 branch.

```python

# this is what I have in mind for this

from ace.analysis import RootAnalysis
from ace.modules.threaded import initialize_modules
from ace.system.threaded import initialize_system

system initialize_system()
modules = initialize_modules()
modules.register()
modules.start()

root = RootAnalysis(description="Example")
observable = root.add_observable('ipv4', '1.2.3.4')
root.submit()

root.wait()
print(root)

```
