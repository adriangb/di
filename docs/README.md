# `di`: pythonic dependency injection

`di` is a modern dependency injection system, modeled around the simplicity of FastAPI's dependency injection.

Key features:

- **Intuitive**: simple things are easy, complex things are possible.
- **Succinct**: declare what you want, and `di` figures out how to assmble it using type annotations.
- **Correct**: tested with MyPy: `value: int = Depends(returns_str)` gives an error.
- **Flexible**: with no fixed scopes, `di` can work within any framework, web or otherwise.
- **Lifespans**: `di` manages lifespans for dependencies by binding them to scopes.
- **Caching**: `di` caches values from dependencies to avoid duplicate computation.
- **Scalability**: `di` executes dependencies in parallel.
- **Performant**: `di` moves sync dependencies into a threadpool to avoid blocking the event loop.

## Installation

<div class="termy">

```console
$ pip install di
---> 100%
```

</div>

!!! warning
    This project is a work in progress.
    Until there is 1.X.Y release, expect breaking changes.

## Examples

### Simple Example

Here is a simple example of how `di` works:

```Python
--8<-- "docs/src/simple.py"
```

### In-depth example

In this example, we'll look at what it would take for a web framework to provide dependecy injection to it's users via `di`.

First we declare a dependency.
We'll call it `Request` like if it were an incoming HTTP request.
This is something the web framework would provide and manage.

```Python hl_lines="4-6"
--8<-- "docs/src/web_framework.py"
```

Next, we'll declare a controller / endpoint that uses the request.
This is the only code the user would have to write.

```Python hl_lines="9-10"
--8<-- "docs/src/web_framework.py"
```

Now we'll define what the web framework needs to do to glue everything together.
This part can get a bit complex, but it's okay because it's written once, in a library.
Users don't need to interact with the container or entering/exiting scopes (although they can if they want to).

We start by creating a container.
This would happen when the app / framework in initialized.

```Python hl_lines="14"
--8<-- "docs/src/web_framework.py"
```

Next, we enter a `"request"` scope.
This would happen for each incoming request.

```Python hl_lines="15"
--8<-- "docs/src/web_framework.py"
```

Note that `"request"` does not have any special meaning to `di`: any hashable value (strings, enums, integers, etc.) will do. Frameworks using `di` need to establish semantic meanings for their scopes and communicate them with their users, but no changes in `di` are necessary to add more socpes.

Next can bind our request instance:

```Python hl_lines="17-18"
--8<-- "docs/src/web_framework.py"
```

!!! tip
    We didn't have to be in the `"request"` scope to do the bind, the opposite order (bind then enter scope) works just as well.

Binds are always a callable.
They can even have their own dependencies (e.g. `container.bind(Dependant(callable_with_dependencies))`) and declare their own scope (see next paragraph).
But in this case we want to use the same `Request` instance everywhere, so we define a lambda that always returns the same instance.

Although not strictly necessary in this case (`Request` is not a context maanger), we pass `scope="request"` to `Dependant` to signify that we want teardown for that dependncy to happen when we exit the `"request"` scope.
If `Request` was a context manager like dependency (a dependency with `yield`), then it's teardown (the section after `yield`) would we run when we exit the `"request"` scope.

Finally, we execute the user's controller / endpoint:

```Python hl_lines="19-20"
--8<-- "docs/src/web_framework.py"
```

When we called `execute()`, `di` checked `controller` and saw that it needed a `Request`. Then it looked at the binds, found the bound provider and injected that.

## Project Aims

This project is primarily geared for enviroments that already use inversion of control (think web frameworks, CLI frameworks or anything else where you define functions and "it calls you").

It particularly excels in async / concurrent environments, since the DI system has first class support for async dependencies and can gather dependencies concurrently.
