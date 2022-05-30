# Scopes

Scopes are one of the fundamental concepts in dependency injection.
Some dependency injection frameworks provide fixed scopes, for example:

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
In Pytest, a `"session"` scoped fixture cannot depend on a `"function"` scoped fixture.

## Inferred scopes

Most of the time you only need to specify scopes for dependencies that have a lifetime coupled to some external event like an HTTP request.
Otherwise, you can leave the scope unspecified or use `None` as the scope and `di` will automatically infer the scope based on the dependency graph.
The rule for this is simple: `di` will pick the highest / outermost valid scope.
The goal of this rule is to:

- Minimize boilerplate (because you don't have to specify a scope in most cases)
- Ensuring optimal caching (by using the outermost scope)
- Reducing errors (because you won't accidentally specify an invalid scope)

```Python
--8<-- "docs_src/inferred_scopes.py"
```

In this example we didn't provide a scope for `get_domain_from_env`, but `di` can see that it does not depend on anything with the `"request"` scope and so it gets assigned the `"singleton"` scope.
On the other hand `authorize` *does* depend on a `Request` object

[contextvars]: https://docs.python.org/3/library/contextvars.html
