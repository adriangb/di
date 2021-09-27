# Solving

Solving a dependency consists of 2 steps:

1. Build a directed acyclic graph of dependencies by inspecting sub dependencies and resolving bind overrides.
1. Topologically sort sub dependencies and group them such that subdependencies that do not depend on eachother can be executed in parallel.

Accordingly, a `SolvedDependency` in `di` corresponds of a DAG of `DependencyProtocol`'s and a topological sort of this DAG.
You can get a `SolvedDependency` via `Container.solve`.
You can then store this value or provide it to `Container.execute_solved` or `Container.get_flat_subdependants`.

!! note
    Internally, `Container.execute` just calls `Container.solve` and `Container.execute_solved`.

During solving, several things are checked:

1. Dependencies must be either autowireable (valid type annotation or explicit mark via `Depends(...)`) or have a bind override.
2. The same dependency is not used twice with different scopes.

However, other things are not checked and are deffered to execution time. Namely, *scopes are not validated during solving*.
This means that you can solve a DAG including `"request"` scoped depdendencies before entering the `"request"` scope.

## Presolving

`di` lets you pre-solve your dependencies so that you don't have to run the solver each time you execute.
This usually comes with a huge performance boost, but only works if you have a static dependency graph (in other words, if you solve than change the DAG, e.g. by introducing a new bind, the solved version will not be updated).
When you have a mostly static graph, but with a single dependency changing (e.g. an incoming web request) you can either:

1. Pre-solve and dynamically replace the nodes in the DAG and topoligcal sort (this is not recommended).
2. Introduce your own way to inject that dependency that preserves the DAG structure. There is an example of this in the [Performance section of the Wiring docs].

## Getting a list of dependencies

`di` provides a convenience function to flatten the dependency DAG into a list off all sub dependencies in `Container.get_flat_subdependants`.

This can be used in conjunction with custom classes implementing the `DependantProtocol` to determine what headers or scopes an HTTP endpoint needs, amongst other uses:

```Python hl_lines="25-30 36-41"
--8<-- "docs/src/gather_deps_example.py"
```

[Performance section of the Wiring docs]: wiring.md#performance
