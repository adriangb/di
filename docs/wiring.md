# Wiring

Wiring is the act of "connecting" together dependencies.
Autowiring means that the container will detect what dependencies are required without the dependencies explicitly being registered with the container.

In order to autowire dependencies, the container will inspect dependencies and find out what their dependencies are and how to construct them.
This type of introspection is generally called _reflection_.
The primary means of inspection are the standard library's `inspect.signature` and `typing.get_type_hints`.
This makes autowiring compatible with a broad range of things, including:

- `def` functions
- Classes
- `functools.partial` binds
- Callable class classes or class instances (classes implementing `__call__`)

Here is an example showing autowiring in action.

Autowiring can work with dataclasses, even ones with a `default_factory`.
In this example we'll load a config from the environment:

```Python hl_lines="7-9"
--8<-- "docs/src/wiring.py"
```

We can also have callable classes as dependencies:

```Python hl_lines="12-18"
--8<-- "docs/src/wiring.py"
```

Notice that we actually have two dependencies here:

- An instance of `DBConn`
- The function `DBConn.__call__`, which requires an instance of `DBConn`

Since we added a type annotation to `DBConn.__call__`'s `self` parameter, `di` will know to inject the instance, but we do have to use `Depends` to declare the dependency explicitly since `DBConn.__call__` is not a valid type annotation.

```Python hl_lines="21"
--8<-- "docs/src/wiring.py"
```

What makes this "autowiring" is that we didn't have to tell `di` how to construct `DBConn`: `di` detected that `controller` needed a `DBConn` and that `DBConn` in turn needs a `Config` instance.

But what about situations where autowiring doesn't cut it?

The most common scenario for this is when type annotations are interfaces / protocols / ABCs, not concrete implementations. This is a good general practice and is very common in larger projects.

Like most other dependency injection frameworks, `di` provides "binds": a way for you to declare to the container that it should replace requests for an interface / abstraction with a concrete implementation.

Binds in `di` are particularly powerful because the bound providers can themselves have dependencies, and those dependencies can even be autowired.

For more information on binds in `di`, see our [Binds] docs.

## Performance

Reflection (inspecting function signatures for dependencies) *is* slow.
For this reason, `di` tries to avoid it as much as possible.
The API is designed around isolating autowiring and execution.
For example, `di` will let you "solve" a dependency into a DAG (directed acyclic graph) and a topological sort of this DAG.
You can then provide this solved dependency back to `di` and it will execute it _without any introspection or reflection_.
This means that if you are not dynamically changing your dependency graph, you incurr basically no cost for autowiring.

For example, here is a more advanced use case where the framework takes control of binding the request itself while still allowing the `di` to controll the rest of the dependencies.
We achieve this by:

1. Binding a static function to provide the current request instance.
1. Using an external method (in this case, [convetxvars]) to inject this instance.

This means that `di` does *not* do any reflection for each request, nor does it have to do dependency resolution.
Instead, only some basic checks on scopes are done and the dependencies are executed with almost no overhead.

```Python
--8<-- "docs/src/solved_dependant.py"
```

[binds]: binds.md
[convetxvars]: https://docs.python.org/3/library/contextvars.html
