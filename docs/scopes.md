# Scopes

Scopes are one of the fundamental concepts in dependency injection.
Some dependency injection frameworks provide fixes scopes, for example:

- Singleton: only one instance is created
- Request: in web frameworks, this could be the lifetime of a request
- Prototype: re-initialized every time it is needed

`di` generalizes this concept by putting control of scopes into the hands of the users / implementers: a scope in `di` is identified by any hashable value (a string, enum, int, etc.) and entering / exiting scopes is handled via context managers:

```python
async with container.enter_global_scope("app"):
    async with container.enter_local_scope(123):
        ...
```

Scopes provide a framework for several other important features:

- Dependency lifespans
- Dependency value sharing

Every dependency is linked to a scope.
When a scope exits, all dependencies linked to it are destroyed (if they have cleanup, the cleanup is run) and their value is no longer available as a share value.
This means that dependencies scoped to an outer scope cannot depend on dependencies scoped to an inner scope:

```Python hl_lines="13 22"
--8<-- "docs/src/invalid_scope_dependance.py"
```

This example will fail with `di.exceptions.ScopeViolationError` because an `"app"` scoped dependency (`conn`, as requested by `controller` via `Depends(scope="app")`) depends on a request scope dependency (in `framework`, we specify `Dependant(..., scope="request"`).
This is because dependencies and scopes behave much a stack and references in general purpose langauges: you can't reference a function local once you exit that function.
Even if we could hold onto the value once we exit the scope, that value could be a reference to an object that already had it's destructor run, for example a database connection that was closed.

## Local vs. global scopes

There are two types of scopes in `di`:

- Local: localized to the current thread/coroutine via [contextvars].
- Global: applied to the `Container` object itself, and hence share by any threads or coroutines that share the same `Container` object.

You can enter a local scope via `Container.enter_local_scope` and a global one via `Container.enter_global_scope`.

This can be useful to share a database connection between requests (global scope) but have each request have it's own local state (local scope), even if multiple requests are handled concurrently.

[contextvars]: https://docs.python.org/3/library/contextvars.html
