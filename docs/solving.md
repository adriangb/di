# Solving

Solving a dependency means build a directed acyclic graph (DAG) of dependencies by inspecting sub dependencies and resolving binds.
Once we solve a dependency, we can execute it without doing any introspection.

Solving is done by the **Container**.
The result of solving is stored in a `SolvedDependent` object which you can pass to `Container.execute_{sync,async}` to get back the result.
The simplest form of executing a dependency is thus:

```python
result = container.execute(container.solve(Dependent(lambda: 1)))
```

For a more comprehensive overview, see the [architecture] section.

## SolvedDependent

`di` lets you pre-solve your dependencies so that you don't have to run the solver each time you execute.
This usually comes with a huge performance boost, but only works if you have a static dependency graph.
In practice, this just means that solving captures the current binds and won't be updated if there are changes to binds.
Note that you can still have *values* in your DAG change, just not the shape of the DAG itself.

For example, here is a more advanced use case where the framework solves the endpoint and then provides the `Request` as a value each time the endpoint is called.

This means that `di` does *not* do any reflection for each request, nor does it have to do dependency resolution.

```Python hl_lines="13-15 18-20"
--8<-- "docs_src/solved_dependent.py"
```

## Getting a list of dependencies

You can easily list all dependencies in a dag via `SolvedDependent.dag.keys()`.

```Python hl_lines="22"
--8<-- "docs_src/solved_dependent.py"
```

This lists all of the *Dependents* for the solved dependency.

This means that you can create custom markers and easily enumerate them.
For example, you might make a `Header` dependency and then want to know what headers are being requested by the controller, even if they are nested inside other dependencies:

```python
from di import Dependent

class Header(Dependent[str]):
    ...
```

See the [dependents] section for a more complete example of this.

[architecture]: architecture.md
[Performance section of the Wiring docs]: wiring.md#performance
[dependents]: dependents.md
