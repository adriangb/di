# Registration and Binding

Provider registration serves two important functions:

- A way to tell the container how to assemble things that can't be auto-wired, for example interfaces.
- A way to override dependencies in tests.

We call a the result of registering a provider a **bind**.

Every bind in `di` consists of:

- A target callable: this can be a function, an interface / protocol or a concrete class
- A substitute dependency: an object implementing the `DependantBase`, usually just an instance of `Dependant`

This means that binds are themselves dependencies:

```Python
--8<-- "docs/src/bind_as_a_dep.py"
```

In this example we register the `Postgres` class to `DBProtocol`, and we can see that `di` auto-wires `Postgres` as well!

Registration can be used as a direct function call, in which case they are permanent, or as a context manager.
