# Concurrency

The core system is designed in such a way that each subsystem can execute independently from the other. A [distributed locking system]() is available to serialize multiple concurrent modification requests to the same object.

## Concurrent Modification Restrictions

The core system must resolve concurrent requests to satisfy analysis results. Analysis results can contain *side effects*. This makes result resolution challenging.

Consider the following scenario: root analysis object Z<sub>1</sub> contains observable O<sub>1</sub>. Two different analysis modules A<sub>1</sub> and A<sub>2</sub> are registered to analyze O<sub>1</sub>. Both analysis modules operate independently.

A<sub>2</sub> finishes first adding an analysis result R<sub>2</sub> to O<sub>1</sub> and adding a tag T<sub>1</sub> to O<sub>1</sub>. Adding the tag is a *side effect*.

A<sub>1</sub> finishes second and adds analysis result R<sub>1</sub> to O<sub>1</sub> but does *not* add a tag.

Due to the side effect, the core system cannot simply replace O<sub>1</sub> when it resolves R<sub>1</sub> because it would overwrite it without the tag that A<sub>2</sub> added to it.

The core system instead *merges* the results together.

## Merging

**Merging** allows one object to be merged into another. There are two types of merging in the core system: *direct* and *differential*. Python classes that support merging will have `apply_merge` and `apply_diff_merge` functions.

### Direct Merge

A **direct merge** takes the form of `target.apply_merge(source)` and copies anything in `source` that is not in `target`.

In our previous example, a direct merge of R<sub>1</sub> into O<sub>1</sub> would *preserve* T<sub>1</sub> because it would only add the analysis result R<sub>1</sub> and do nothing else.

Likewise, if R<sub>1</sub> finished first, then a direct merge of R<sub>2</sub> O<sub>1</sub> would *add* T<sub>1</sub> into O<sub>1</sub> because T<sub>1</sub> does not exist in the target.

There is another scenario that requires additional logic to handle. Consider the following: root analysis object Z<sub>1</sub> contains observable O<sub>1</sub>. Two different analysis modules A<sub>1</sub> and A<sub>2</sub> are registered to analyze O<sub>1</sub>. Both analysis modules operate independently.

A<sub>1</sub> finishes first and adds analysis result R<sub>1</sub> to O<sub>1</sub>, but also changes the `analysis_mode` property of Z<sub>1</sub> from `analysis` to `correlation`. This change to Z<sub>1</sub> is a *side effect*.

A<sub>2</sub> finishes second and adds analysis result R<sub>2</sub> to O<sub>1</sub>. However, it does not change the `analysis_mode` property of Z<sub>1</sub>.

At this point, the core system has no idea if A<sub>2</sub> left the property alone or if it *changed it back*.

### Differential Merge

A **differential merge** applies the changes (delta) between two objects to a target object. It takes the form of `target.apply_diff_merge(before, after)` where `target` is the object to receive the changes, `before` is the state of the object before the changes were made, and `after` is the state of the object after the changes were made.

If we apply this to the previous scenario, the differential merge would see that the `analysis_mode` property was the same in both the `before` and `after` objects, so R<sub>2</sub> would *not* overwrite the property with the wrong value.
