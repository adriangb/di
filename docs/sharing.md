# Dependency sharing

Often, you will have dependencies that share a sub dependency.
For example, you probably only want to load your configuration from enviroment variables *once* and then re-use the same object in multiple dependencies.
In `di`, we call this concept *dependency sharing*.

## How sharing works

Dependencies are identfied by their callable provider.
This could be the constructor for a type or an arbitrary callable encapsulated using `Depends(...)`.
By default, dependencies are shared, but this behavior can be changed on a per-dependency basis using the `share=False` parameter.

```Python hl_lines="7-9"
--8<-- "docs/src/sharing.py"
```

## Sharing and scopes

Dependencies are share within their scope and any innner scopes.
Once a dependency's scope exits, it's share value is discareded and the next time the scope is entered a fresh value will be computed.
