# Dependency Cache

Often, you will have dependencies that share a sub dependency.
For example, you probably only want to load your configuration from environment variables *once* and then re-use the same object in multiple dependencies.
To avoid re-computing the shared dependency, `di` will cache shared dependencies.

## How caching works

Dependencies are cached by their cache key, computed in `Dependant.cache_key`.
See [dependants] for more information on `Dependant.cache_key`.
Dependencies are cached by default, but this behavior can be changed on a per-dependency basis using the `use_cache=False` parameter.

```Python hl_lines="8-13"
--8<-- "docs_src/sharing.py"
```

## Caching and scopes

Dependencies are cached within their scope and any inner scopes.
Once a dependency's scope exits, it's cached value is discarded and the next time the scope is entered a fresh value will be computed.

[dependants]: dependants.md
