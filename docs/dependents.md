# Dependents and the DependentBase

Most of these docs use `Dependent` as the main marker for dependencies.
But the container doesn't actually know about either of these two things!
In fact, the container only knows about the `DependentBase`, which you can find in `di.api.dependencies`.
`Dependent` is just one possible implementation of the `DependentBase`.

You can easily build your own version of `Dependent` by inheriting from `Dependent` or `DependentBase`.

Here is an example that extracts headers from requests:

```python
--8<-- "docs_src/headers_example.py"
```

Another good example of the flexibility provided by `DependentBase` is the implementation of [JointDependent], which lets you schedule and execute dependencies together even if they are not directly connected by wiring:

```python
--8<-- "docs_src/joined_dependent.py"
```

Here `B` is executed even though `A` does not depend on it.
This is because `JoinedDependent` leverages the `DependentBase` interface to tell `di` that `B` is a dependency of `A` even if `B` is not a parameter or otherwise related to `A`.

[Solving docs]: solving.md
[JointDependent]: https://github.com/adriangb/di/blob/b7398fbdf30213c1acb94b423bb4f2e2badd0fdd/di/dependent.py#L194-L218
