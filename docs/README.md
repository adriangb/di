# `di`: pythonic dependency injection

`di` is a modern dependency injection system, modeled around the simplicity of FastAPI's dependency injection.

Key features:

- **Intuitive**: simple things are easy, complex things are possible.
- **Succinct**: declare what you want, and `di` figures out how to assmble it using type annotations.
- **Correct**: tested with MyPy: `value: int = Depends(returns_str)` gives an error.
- **Flexible**: with no fixed scopes, `di` can work within any framework, web or otherwise.
- **Lifespans**: `di` manages lifespans for dependencies by binding them to scopes.
- **Caching**: `di` caches values from dependencies to avoid duplicate computation.
- **Scalability**: `di` executes dependencies in parallel and only needs to solve them once.
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

Let's start by looking at the User's code.

```Python hl_lines="15-22"
--8<-- "docs/src/web_framework.py"
```

As a user, you have very little boilerplate.
In fact, there is not a single LOC here that is not transmitting information.

Now let's look at the web framework side of things.
This part can get a bit complex, but it's okay because it's written once, in a library.

First, we'll need to create a `Container` instance.
This would be tied to the `App` or `Router` instance of the web framwork.

```Python hl_lines="9"
--8<-- "docs/src/web_framework.py"
```

Next, we "solve" the users endpoint:

```Python hl_lines="10"
--8<-- "docs/src/web_framework.py"
```

This should happen once, maybe at app startup.
The framework can then store the `solved` object, which contains all of the information necessary to execute the dependency (dependency being in this case the user's endpoint/controller function).
This is very important for performance: we want do the least amount of work possible for each incoming request.

Finally, we execute the endpoint for each incoming request:

```Python hl_lines="11"
--8<-- "docs/src/web_framework.py"
```

When we do this, we provide the `Request` instance as a value.
This means that `di` does not introspect at all into the `Request` to figure out how to build it, it just hands the value off to anything that requests it.
You can also "bind" providers, which is covered in the [binds] section of the docs.

## Project Aims

This project is primarily geared for enviroments that already use inversion of control (think web frameworks, CLI frameworks or anything else where you define functions and "it calls you").

It particularly excels in async / concurrent environments, since the DI system has first class support for async dependencies and can gather dependencies concurrently.

[binds]: binds.md
