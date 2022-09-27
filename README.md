# `di`: dependency injection toolkit

<p align="center">
<a href="https://github.com/adriangb/di/actions?query=workflow%3ACI%2FCD+event%3Apush+branch%3Amain" target="_blank">
    <img src="https://github.com/adriangb/di/actions/workflows/workflow.yaml/badge.svg?event=push&branch=main" alt="Test">
</a>
<a href="https://codecov.io/gh/adriangb/di" target="_blank">
    <img src="https://img.shields.io/codecov/c/github/adriangb/di?color=%2334D058" alt="Coverage">
</a>
<a href="https://pypi.org/project/di" target="_blank">
    <img src="https://img.shields.io/pypi/v/di?color=%2334D058&label=pypi%20package" alt="Package version">
</a>
<a href="https://pypi.org/project/di" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/di.svg?color=%2334D058" alt="Supported Python versions">
</a>
</p>

`di` is a modern dependency injection toolkit, modeled around the simplicity of FastAPI's dependency injection.

Key features:

- **Intuitive**: simple API, inspired by [FastAPI].
- **Auto-wiring**: `di` supports auto-wiring using type annotations.
- **Scopes**: inspired by [pytest scopes], but defined by users (no fixed "request" or "session" scopes).
- **Composable**: decoupled internal APIs give you the flexibility to customize wiring, execution and binding.
- **Performant**: `di` can execute dependencies in parallel and cache results ins scopes. Performance critical parts are written in [🦀] via [graphlib2].

## Installation

```shell
pip install di[anyio]
```

⚠️ This project is a work in progress. Until there is 1.X.Y release, expect breaking changes. ⚠️

## Simple Example

Here is a simple example of how `di` works:

```python
from dataclasses import dataclass

from di import Container, Dependant, SyncExecutor


class A:
    ...


class B:
    ...


@dataclass
class C:
    a: A
    b: B


def main():
    container = Container()
    executor = SyncExecutor()
    solved = container.solve(Dependant(C, scope="request"), scopes=["request"])
    with container.enter_scope("request") as state:
        c = container.execute_sync(solved, executor=executor, state=state)
    assert isinstance(c, C)
    assert isinstance(c.a, A)
    assert isinstance(c.b, B)
```

For more examples, see our [docs].

### Why do I need dependency injection in Python? Isn't that a Java thing?

Dependency injection is a software architecture technique that helps us achieve [inversion of control] and [dependency inversion] (one of the five [SOLID] design principles).

It is a common misconception that traditional software design principles do not apply to Python.
As a matter of fact, you are probably using a lot of these techniques already!

For example, the `transport` argument to httpx's Client ([docs](https://www.python-httpx.org/advanced/#custom-transports)) is an excellent example of dependency injection. Pytest, arguably the most popular Python test framework, uses dependency injection in the form of [pytest fixtures].

Most web frameworks employ inversion of control: when you define a view / controller, the web framework calls you! The same thing applies to CLIs (like [click]) or TUIs (like [Textual]). This is especially true for many newer web frameworks that not only use inversion of control but also dependency injection. Two great examples of this are [FastAPI] and [BlackSheep].

For a more comprehensive overview of Python projects related to dependency injection, see [Awesome Dependency Injection in Python].

## Project Aims

This project aims to be a dependency injection toolkit, with a focus on providing the underlying dependency injection functionality for other libraries.

In other words, while you could use this as a standalone dependency injection framework, you may find it to be a bit terse and verbose. There are also much more mature standalone dependency injection frameworks; I would recommend at least looking into [python-dependency-injector] since it is currently the most popular / widely used of the bunch.

For more background, see our [docs].

[🦀]: https://www.rust-lang.org
[graphlib2]: https://github.com/adriangb/graphlib2
[docs]: https://www.adriangb.com/di/
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
