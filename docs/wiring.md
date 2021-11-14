# Wiring

Wiring is the act of "connecting" together dependencies.
There are generally two types of wiring that a DI container can do:

- Autowiring: where the container inspects the dependencies and automatically deduces their sub-dependencies.
- Manual wiring: where the user needs to register each sub-dependency with the container.

Autowiring is generally preferrable: it reduces boilerplate and decouples your application from the Container's API.
But autowiring is not always possible: sometimes the value is produced by a function (`value: int = some_function()`) or the type to inject is not the type in the annotation (when using interfaces / protocols).

## Autowiring in `di`

Autowiring in `di` relies on inspecting function signatures and class constructors.
The primary means of inspection are the standard library's `inspect.signature` and `typing.get_type_hints`.
This makes autowiring compatible with a broad range of things, including:

- `def` functions
- Classes
- `functools.partial` binds
- Callable class classes or class instances (classes implementing `__call__`)

Here is an example showing autowiring in action.

Autowiring can work with dataclasses, even ones with a `default_factory`.
In this example we'll load a config from the environment:

```Python
--8<-- "docs/src/autowiring.py"
```

What makes this "autowiring" is that we didn't have to tell `di` how to construct `DBConn`: `di` detected that `controller` needed a `DBConn` and that `DBConn` in turn needs a `Config` instance.

## Manual wiring

But what about situations where autowiring doesn't cut it?
A common scenario for this is when type annotations are interfaces / protocols / ABCs, not concrete implementations. This is a good general practice and is very common in larger projects.
It is also common for a dependency to come from a function, in which case we don't just want an instance of the type annotation, we want the value returned by a specific function.

In these scenarios, some manual input from the user is required.
There are two important concepts in `di` to handle this input:

- Binds: are used to swap out one dependency for another, which can be used to swap out an interface / protocol / ABC for a concrete implementation.
- Markers: usually `Depends(...)` which tell `di` how to construct the dependency (e.g. calling a function) as well as carrying other meteadata (like the scope, which you will see more about later on).

Here is an example that makes use of both:

```Python
--8<-- "docs/src/manual_wiring.py"
```

Binds in `di` are particularly powerful because the bound providers can themselves have dependencies, and those dependencies can even be autowired.
For more information on binds in `di`, see our [Binds] docs.

Markers can be set either as default values or via [PEP 593 Annotated].
There are advantages and disadvantages to each method:

### Annotated

#### Pros of Annotated

- Compatible with other uses of default values, like dataclass' `field` or Pydantic's `Field`.
- Non-invasive modification of signatures: adding `Depends(...)` in `Annotated` should be ignored by anything except `di`.
- Functions/classes can be called as normal outside of `di` and the default values (when present) will be used.

#### Cons of Annotated

- Types will not be checked: `def func(v: Anotated[int, Depends(lambda: "a")])` does not produce an error in MyPy or Pylance.
- `Annotated` requires Python 3.9 (although it is available via the [typing_extensions backport])
- Using `Annotated` is more verbose, and can easily cause your function signature to spill into multiple lines.

### Default values

#### Pros of default values

- Incompatible with other uses of default values, like dataclass' `field` or Pydantic's `Field`.
- Having a default value in addition to `Depends` requires some customization of `Dependant` (to add a `default: Any` argument).

#### Cons of default values

- Types will be checked: `def func(v: int = Depends(lambda: "a"))` produces an error in MyPy or Pylance.
- Function/class can no longer be called outside of `di` without passing values: you would get an instance of `DependantBase` as the default value.

Overall, use of `Annotated` is preferable to reduce coupling between `di` and your code, but using default values can make sense in some scenarios.

## Performance

Reflection (inspecting function signatures for dependencies) *is* slow.
For this reason, `di` tries to avoid it as much as possible.
The best way to avoid extra introspection is to re-use [Solved Dependants].

[Solved Dependants]: solving.md#SolvedDependant
[binds]: binds.md
[PEP 593 Annotated]: https://www.python.org/dev/peps/pep-0593/
[typing_extensions backport]: https://pypi.org/project/typing-extensions/
