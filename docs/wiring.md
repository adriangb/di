# Wiring

Wiring is the act of "connecting" together dependencies.

In `di`, wiring is handled by the `Dependant` API.
The general idea is that `Container` accepts a `Dependant` and then asks it for it's sub-dependencies.
These sub-dependencies are themselves `Dependant`s, and so the `Container` keeps asking them for _their_ sub-dependenices until there are none.

But how does `Dependant` know what it's dependencies are?
Every `Dependant` has a `call` attribute which is a callable (a class, a function, etc.) that which can be introspected (usually with `inpsect.signature`) to find it's parameters.
The from these parameters the `Dependant` determine's what it's dependencies are.
But how do we go from a parameter `param: Foo` to a `Dependant`?
There are actually several different mechanisms available:

## Autowiring

Autowiring is available when the parameter's type annotation is a well-behaved type/class. Well behaved in this case means just means that it's parameters can be understood by `di`, for example that they are type annotated and are uniquely identifiable (`param: int` won't work properly).

Here is an example showing auto-wiring in action.

Auto-wiring can work with dataclasses, even ones with a `default_factory`.
In this example we'll load a config from the environment:

```Python
--8<-- "docs_src/autowiring.py"
```

What makes this "auto-wiring" is that we didn't have to tell `di` how to construct `DBConn`: `di` detected that `controller` needed a `DBConn` and that `DBConn` in turn needs a `Config` instance.

This is the simplest option because you don't have to do anything, but it' relatively limited in terms of what can be injected.

!!! note Dependant metadata inheritence
    You'll notice that we gave our root dependency a `scope` but did not do the smae with our other dependencies.
    When `Dependant` auto-wires it's sub-dependants, they'll inherit it's scope.
    So every dependendency in this example ends up with the `"request"` scope.

## Dependency markers

Dependency markers, in the form of `di.dependant.Marker` serve to hold information about a dependency, for example how to construct it or it's scope.

Markers are generally useful when:

- Injecting a non-identifiabletype, like a `list[str]`
- Injecting the result of a function (`param: some_function` is not valid in Python)
- The type being injected is not well-behaved and you need to tell `di` how to construct it

Let's take our previous example and look at how we would have used markers if `DBConn` accepted a `host: str` paramter instead of our `Config` class directly:

```Python
--8<-- "docs_src/markers.py"
```

All we had to do was tell `di` how to construct `DBConn` (by assigning the parameter a `Marker`) and `di` can do the rest.
Note that we are still using autowiring for `endpoint` and `Config`, it's not all or nothing and you can mix and match styles.

### A note on Annotated / PEP 593

Markers are set via [PEP 593's Annotated].
This is in contrast to FastAPIs use of markers as default values (`param: int = Depends(...)`).
When FastAPI was designed, PEP 593 did not exist, and there are several advantages to using PEP 593's Annotated:

- Compatible with other uses of default values, like dataclass' `field` or Pydantic's `Field`.
- Non-invasive modification of signatures: adding `Marker(...)` in `Annotated` should be ignored by anything except `di`.
- Functions/classes can be called as normal outside of `di` and the default values (when present) will be used.
- Multiple markers can be used. For example, something like `Annotated[T, PydanticField(), Marker()]`.

This last point is important because of the composability it provides:

```python
from typing import TypeVar, Annotated

from di import Marker
from pydantic import Field

T_int = TypeVar("T_int", bound=int)
PositiveInt = Annotated[T_int, Field(ge=0)]

T = TypeVar("T")
Depends = Annotated[T, Marker()]

def foo(v: Depends[PositiveInt[int]]) -> int:
    return v
```

Note how we used [type aliases] to create stackable, reusable types.
This means that while `Annotated` can sometimes be verbose, it can also be made very convenient with type aliases.

[type aliases]: https://www.python.org/dev/peps/pep-0593/#aliases-concerns-over-verbosity

## Custom types

If you are writing and injecting your own classes, you also have the option of putting the dependency injection metadata into the class itself, via the `__di_dependency__(cls) -> Marker` protocol. This obviously doesn't work if you are injecting a 3rd party class you are importing (unless you subclass it).

The main advantage of this method is that the consumers of this class (wich may be your own codebase) don't have to apply markers everywhere or worry about inconsistent scopes (see [scopes]).

For example, we can tell `di` constructing a class asynchronously`:

```Python
--8<-- "docs_src/async_constructor.py"
```

This allows you to construct your class even if it depends on doing async work _and_ it needs to refer to the class itself.

If you only need to do async work and don't need access to the class, you don't need to use this and can instead just make your field depend on an asynchronous function:

```Python
--8<-- "docs_src/async_init_dependency.py"
```

Another way this is useful is to pre-declare scopes for a class.
For example, you may only want to have one `UserRepo` for you entire app:

```Python
--8<-- "docs_src/singleton.py"
```

[scopes]: scopes.md

### InjectableClass

As a convenience, `di` provides an `InjectableClass` type that you can inherit from so that you can easily pass parameters to `Marker` without implementing `__di_dependant__`:

```Python
--8<-- "docs_src/injectable_class.py"
```

## Binds

Binds, which will be covered in depth in the [binds] section offer a way of swapping out dependencies imperatively (when you encounter type "X", use function "y" to build it).
They can be used with any of the methods described above.

## Performance

Reflection (inspecting function signatures for dependencies) _is very slow_.
For this reason, `di` tries to avoid it as much as possible.
The best way to avoid extra introspection is to re-use [Solved Dependants].

## Conclusion

There are several ways to declare dependencies in `di`.
Which one makes sense for each use case depends on several factors, but ultimately they all achieve the same outcome.

[Solved Dependants]: solving.md#SolvedDependant
[binds]: binds.md
[PEP 593's Annotated]: https://www.python.org/dev/peps/pep-0593/
[typing_extensions backport]: https://pypi.org/project/typing-extensions/
