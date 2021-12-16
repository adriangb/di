# `di`: pythonic dependency injection

`di` is a modern dependency injection system, modeled around the simplicity of FastAPI's dependency injection.

Key features:

- **Intuitive**: simple API, inspired by [FastAPI].
- **Succinct**: declare what you want, and `di` figures out how to assmble it using type annotations.
- **Correct**: tested with MyPy: `value: int = Depends(returns_str)` gives an error.
- **Scopes**: inspired by [pytest scopes], but defined by users (no fixed "request" or "session" scopes).
- **Flexible**: decoupled internal APIs give you the flexibility to customize wiring and execution.
- **Performant**: `di` can execute dependencies in parallel, move sync dependencies to threads and cache results. Performance critical parts are written in 🦀.

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

### Why do I need dependency injection in Python? Isn't that a Java thing?

Dependency injection is a software architecture technique that helps us achieve [inversion of control] and [dependency inversion] (one of the five [SOLID] design principles).

It is a common misconception that traditional software design principles do not apply to Python.
As a matter of fact, you are probably using a lot of these techniques already!

For example, the `transport` argument to httpx's Client ([docs](https://www.python-httpx.org/advanced/#custom-transports)) is an excellent example of dependency injection. Pytest, arguably the most popular Python test framework, uses dependency injection in the form of [pytest fixtures].

Most web frameworks employ inversion of control: when you define a view / controller, the web framework calls you! The same thing applies to CLIs (like [click]) or TUIs (like [Textual]). This is especially true for many newer webframeworks that not only use inversion of control but also dependency injection. Two great examples of this are [FastAPI] and [BlackSheep].

For a more comprehensive overview of Python projectes related to dependency injection, see [Awesome Dependency Injection in Python].

## Project Aims

This project aims to be a general dependency injection system, with a focus on providing the underlaying dependency injection functionality for other libaries.

In other words, while you could use this as your a standalone dependency injection framework, you may find it to be a bit terse and verbose. There are also much more mature standalone dependency injection frameworks; I would recommend at least looking into [python-dependency-injector] since it is currently the most popular / widely used of the bunch.

### In-depth example

With this background in place, let's dive into a more in-depth example.

In this example, we'll look at what it would take for a web framework to provide dependecy injection to it's users via `di`.

Let's start by looking at the User's code.

```Python hl_lines="17-27"
--8<-- "docs/src/web_framework.py"
```

As a user, you have very little boilerplate.
In fact, there is not a single line of code here that is not transmitting information.

Now let's look at the web framework side of things.
This part can get a bit complex, but it's okay because it's written once, in a library.

First, we'll need to create a `Container` instance.
This would be tied to the `App` or `Router` instance of the web framwork.

```Python hl_lines="11"
--8<-- "docs/src/web_framework.py"
```

Next, we "solve" the users endpoint:

```Python hl_lines="12"
--8<-- "docs/src/web_framework.py"
```

This should happen once, maybe at app startup.
The framework can then store the `solved` object, which contains all of the information necessary to execute the dependency (dependency being in this case the user's endpoint/controller function).
This is very important for performance: we want do the least amount of work possible for each incoming request.

Finally, we execute the endpoint for each incoming request:

```Python hl_lines="13-14"
--8<-- "docs/src/web_framework.py"
```

When we do this, we provide the `Request` instance as a value.
This means that `di` does not introspect at all into the `Request` to figure out how to build it, it just hands the value off to anything that requests it.
You can also "bind" providers, which is covered in the [binds] section of the docs.

[binds]: binds.md
[dependency inversion]: https://en.wikipedia.org/wiki/Dependency_inversion_principle
[SOLID]: https://en.wikipedia.org/wiki/SOLID
[inversion of control]: https://en.wikipedia.org/wiki/Inversion_of_control
[click]: https://click.palletsprojects.com/en/8.0.x/
[Textual]: https://github.com/willmcgugan/textual
[FastAPI]: https://fastapi.tiangolo.com/tutorial/dependencies/
[BlackSheep]: https://www.neoteroi.dev/blacksheep/dependency-injection/
[Awesome Dependency Injection in Python]: https://github.com/sfermigier/awesome-dependency-injection-in-python
[python-dependency-injector]: https://github.com/ets-labs/python-dependency-injector
[pytest scopes]: https://docs.pytest.org/en/6.2.x/fixture.html#scope-sharing-fixtures-across-classes-modules-packages-or-session
[pytest fixtures]: https://docs.pytest.org/en/6.2.x/fixture.html
