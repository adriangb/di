# Dependants and the DependantProtocol

Most of these docs use `Depends` and `Dependency` as the main markers and containers for dependencies.
But the container doesn't actually know about either of these two things!
In fact, the container only knows about the `DependantProtocol`, which you can find in `di.dependency`.
`Dependency` is just a concrete implementation of the `DependantProtocol`, and `Depends` is in turn a wrapper function around `Dependency` for the sole purpose of overriding the types that type checkers see.

You can easily build your own version of `Dependency` and `Depends`, either by inheriting from `Dependency` or by writing a `DependantProtocol` implementation from scratch.

There are many use cases for this, including:

1. Carrying extra data in the marker by making a class that accepts extra arguments in `__init__`.
2. Providing a callable implementation that depends on user defined parameters.
3. Hiding options like `scope` or `share` from users where it does not make sense to change them.

An example of creating Security dependencies for a web framework is available in the the [Solving docs].

Here is another example that extracts headers from requests:

```Python
--8<-- "docs/src/headers_example.py"
```

[Solving docs]: solving.md
