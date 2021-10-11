# Solving

Solving a dependency consists of 2 steps:

1. Build a directed acyclic graph of dependencies by inspecting sub dependencies and resolving bind overrides.
1. Topologically sort sub dependencies and group them such that subdependencies that do not depend on eachother can be executed in parallel.

Accordingly, a `SolvedDependency` in `di` corresponds of a DAG of `DependencyProtocol`'s and a topological sort of this DAG.
You can get a `SolvedDependency` via `Container.solve`.
You can then store this value or provide it to `Container.execute_sync` or `Container.execute_async`.

During solving, several things are checked:

1. Any dependencies that can't be fully autowirired have binds.
2. The same dependency is not used twice with different scopes.

However, other things are not checked and are deffered to execution time. Namely, *scopes are not validated during solving*.
This means that you can solve a DAG including `"request"` scoped depdendencies before entering the `"request"` scope.

## SolvedDependant

`di` lets you pre-solve your dependencies so that you don't have to run the solver each time you execute.
This usually comes with a huge performance boost, but only works if you have a static dependency graph.
In practice, this just means that solving captures the current binds and won't be updated if there are changes to binds.
Note that you can still have *values* in your DAG change, just not the shape of the DAG itself.

For example, here is a more advanced use case where the framework solves the endpoint and then provides the `Request` as a value each time the endpoint is called.

This means that `di` does *not* do any reflection for each request, nor does it have to do dependency resolution.
Instead, only some basic checks on scopes are done and the dependencies are executed with almost no overhead.

```Python hl_lines="23 31"
--8<-- "docs/src/solved_dependant.py"
```

To disable scope checks (perhaps something reasonable to do in a web framework after 1 request is processed), you can pass the `validate_scopes=False` parameter to `execute_sync` or `execute_async`.

## Getting a list of dependencies

`di` provides a convenience function to flatten the dependency DAG into a list off all sub dependencies in `Container.get_flat_subdependants`.

This can be used in conjunction with custom classes implementing the `DependantProtocol` to determine what headers or scopes an HTTP endpoint needs, amongst other uses:

```Python hl_lines="27-32 38-42"
--8<-- "docs/src/gather_deps_example.py"
```

[Performance section of the Wiring docs]: wiring.md#performance
