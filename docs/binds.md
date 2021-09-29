# Binds

Binds provide two important functions:

- A way to tell the container how to assemble things that can't be autowired, for example interfaces.
- A way to override dependencies in tests.

Every bind in `di` consists of:

- A target callable: this can be a function, an interface / protocol or a concrete class
- A substitute dependency: an object implementing the `DependencyProtocol`, usually just an instance of `Dependant`

This means that binds are themselves dependencies:

```Python
--8<-- "docs/src/bind_as_a_dep.py"
```

In this example we bind a concrete `Postgres` instance to `DBProtocol`, and we can see that `di` autowires `Postgres` as well!

Binds can be used as a direct function call, in which case they are permanent, or as a context manager.
