# Scopes

Scopes are one of the fundamental concepts in dependency injection.
Some dependency injection frameworks provide fixes scopes, for example:

- Singleton: only one instance is created
- Request: in web frameworks, this could be the lifetime of a request
- Prototype: re-initialized every time it is needed

`di` generalizes this concept by putting control of scopes into the hands of the users / implementers: a scope in `di` is identified by any hashable value (a string, enum, int, etc.) and entering / exiting scopes is handled via context managers:

```python
async with container.enter_scope("app"):
    async with container.enter_scope("request"):
        async with container.enter_scope("foo, bar, baz!"):
```

Scopes provide a framework for several other important features:

- Dependency lifespans
- Dependency value sharing

Every dependency is linked to a scope.
When a scope exits, all dependencies linked to it are destroyed (if they have teardown, the teardown is run) and their value is removed from the cache.
This means that dependencies scoped to an outer scope cannot depend on dependencies scoped to an inner scope:

```Python
--8<-- "docs_src/invalid_scope_dependance.py"
```

This example will fail with `di.exceptions.ScopeViolationError` because an `DBConnection` is scoped to `"app"` so it cannot depend on `Request` which is scoped to `"request"`.
The order of the scopes is determined by the `scopes` parameter to `Container.solve`.
If you've used Pytest fixtures before, you're already familiar with these rules.
In Pytest, a `"session"` scoped fixtrue cannot depend on a `"function"` scoped fixture.

[contextvars]: https://docs.python.org/3/library/contextvars.html
