# Dependants and the DependantBase

Most of these docs use `Depends` and `Dependency` as the main markers and containers for dependencies.
But the container doesn't actually know about either of these two things!
In fact, the container only knows about the `DependantBase`, which you can find in `di.api.dependencies`.
`Dependency` is just a concrete implementation of the `DependantBase`, and `Depends` is in turn a wrapper function around `Dependency` for the sole purpose of overriding the types that type checkers see.

You can easily build your own version of `Dependency` and `Depends`, by inheriting from `Dependency` or by writing a `DependantBase` implementation from scratch.

!!! note
    `DependantBase` is a relatively simple interface.
    We choose to use an ABC primarily so that it is inexpensive to do `isinstance(something, DependantBase)`, which comes up relatively often.
    Unlike ABCs, Protocols cannot be cheaply or accurately runtime checked in Python.

Here is an example that extracts headers from requests:

```python
--8<-- "docs/src/headers_example.py"
```

Another good example of the customizability provided by `DependantBase` is the implementation of [JointDependant], which lets you schedule and execute dependencies together even if they are not directly connected by wiring:

```python
--8<-- "docs/src/joined_dependant.py"
```

Here `B` is executed even though `A` does not depend on it.
This is because `JoinedDependant` leverages the `DependantBase` interface to tell `di` that `B` is a dependency of `A` even if `B` is not a parameter or otherwise related to `A`.

[Solving docs]: solving.md
[JointDependant]: https://github.com/adriangb/di/blob/b7398fbdf30213c1acb94b423bb4f2e2badd0fdd/di/dependant.py#L194-L218
