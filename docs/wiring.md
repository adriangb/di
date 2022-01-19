# Wiring

Wiring is the act of "connecting" together dependencies.
There are generally two types of wiring that a DI container can do:

- Auto-wiring: where the container inspects the dependencies and automatically deduces their sub-dependencies.
- Manual wiring: where the user needs to register each sub-dependency with the container.

Auto-wiring is generally preferable: it reduces boilerplate and decouples your application from the Container's API.
But auto-wiring is not always possible: sometimes the value is produced by a function (`value: int = some_function()`) or the type to inject is not the type in the annotation (when using interfaces / protocols).

## Auto-wiring in `di`

Auto-wiring in `di` relies on inspecting function signatures and class constructors.
The primary means of inspection are the standard library's `inspect.signature` and `typing.get_type_hints`.
This makes auto-wiring compatible with a broad range of things, including:

- `def` functions
- Classes
- `functools.partial` binds
- Callable class classes or class instances (classes implementing `__call__`)

Here is an example showing auto-wiring in action.

Auto-wiring can work with dataclasses, even ones with a `default_factory`.
In this example we'll load a config from the environment:

```Python
--8<-- "docs/src/auto-wiring.py"
```

What makes this "auto-wiring" is that we didn't have to tell `di` how to construct `DBConn`: `di` detected that `controller` needed a `DBConn` and that `DBConn` in turn needs a `Config` instance.

## Manual wiring

But what about situations where auto-wiring doesn't cut it?
A common scenario for this is when type annotations are interfaces / protocols / ABCs, not concrete implementations. This is a good general practice and is very common in larger projects.
It is also common for a dependency to come from a function, in which case we don't just want an instance of the type annotation, we want the value returned by a specific function.

In these scenarios, some manual input from the user is required.
There are two important concepts in `di` to handle this input:

- Binds: are used to swap out one dependency for another, which can be used to swap out an interface / protocol / ABC for a concrete implementation.
- Markers: usually `Dependant(...)` which tell `di` how to construct the dependency (e.g. calling a function) as well as carrying other metadata (like the scope, which you will see more about later on).

Here is an example that makes use of both:

```Python
--8<-- "docs/src/manual_wiring.py"
```

Binds in `di` are particularly powerful because the bound providers can themselves have dependencies, and those dependencies can even be auto-wired.
For more information on binds in `di`, see our [Binds] docs.

Markers are set via [PEP 593's Annotated].
This is in contrast to FastAPIs use of markers as default values (`param: int = Depends(...)`).
When FastAPI was designed, PEP 593 did not exist, and there are several advantages to using PEP 593's Annotated:

- Compatible with other uses of default values, like dataclass' `field` or Pydantic's `Field`.
- Non-invasive modification of signatures: adding `Depends(...)` in `Annotated` should be ignored by anything except `di`.
- Functions/classes can be called as normal outside of `di` and the default values (when present) will be used.
- Multiple markers can be used. For example, something like `Annotated[T, SyncToThread(), Depends()]` is possible, or even `Annotated[Annotated[T, Dependant()], SyncToThread()]` (which is equivalent). With the aliases `Provide = Annotated[T, Depends()]` and `InThread = Annotated[T, SyncToThread()]` one can write `Provide[InThread[SomeClass]]`.

There are however some cons to the use of `Annotated`:

- `Annotated` requires Python 3.9 (although it is available via the [typing_extensions backport])
- Using `Annotated` is more verbose, and can easily cause your function signature to spill into multiple lines.

## Performance

Reflection (inspecting function signatures for dependencies) *is* slow.
For this reason, `di` tries to avoid it as much as possible.
The best way to avoid extra introspection is to re-use [Solved Dependants].

[Solved Dependants]: solving.md#SolvedDependant
[binds]: binds.md
[PEP 593's Annotated]: https://www.python.org/dev/peps/pep-0593/
[typing_extensions backport]: https://pypi.org/project/typing-extensions/
