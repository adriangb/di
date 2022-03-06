# Binds

Provider binding serves two important functions:

- A way to tell the container how to assemble things that can't be auto-wired, for example interfaces.
- A way to override dependencies in tests.

Every bind in `di` consists of:

- A target callable: this can be a function, an interface / protocol or a concrete class
- A substitute dependency: an object implementing the `DependantBase`, usually just an instance of `Dependant`

This means that binds are themselves dependencies:

```Python
--8<-- "docs_src/bind_as_a_dep.py"
```

In this example we register the `Postgres` class to `DBProtocol`, and we can see that `di` auto-wires `Postgres` as well!

Binds can be used as a direct function call, in which case they are permanent, or as a context manager, in which case they are reversed when the context manager exits.

## Bind hooks

Binding is implemented as hooks / callbacks: when we solve a dependency graph, every hook is called with every dependant and if the hook "matches" the dependent it returns the substitute dependency (otherwise it just returns `None`).

This means you can implement any sort of matching you want, including:

- Matching by type (see `di.container.bind_by_type`)
- Matching by any subclass (`di.container.bind_by_type` using the `covariant=True` parameter)
- Custom logic, in the form of a bind hook (`Container.bind`)

For example, to match by parameter name:

```Python
--8<-- "docs_src/bind_hooks.py"
```
