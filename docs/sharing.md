# Dependency sharing

Often, you will have dependencies that share a sub dependency.
For example, you probably only want to load your configuration from environment variables *once* and then re-use the same object in multiple dependencies.
In `di`, we call this concept *dependency sharing*.

## How sharing works

Dependencies are usually identified by their callable provider (see [dependants] for ways in which you can change this).
This could be the constructor for a type or an arbitrary callable encapsulated using `Depends(...)`.
By default, dependencies are shared, but this behavior can be changed on a per-dependency basis using the `share=False` parameter.

```Python hl_lines="7-9"
--8<-- "docs/src/sharing.py"
```

## Sharing and scopes

Dependencies are share within their scope and any inner scopes.
Once a dependency's scope exits, it's share value is discarded and the next time the scope is entered a fresh value will be computed.

[dependants]: dependants.md
