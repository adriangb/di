# Integrations

We do not provide any fully supported 3rd party integrations as of this moment.
However, `di` is designed to easily be integrated into existing frameworks.

Below are some samples that show how `di` might be used by web frameworks and other applications.
These examples are only for demonstration, and are missing critical features that would be required for a full fledged integration.

The integrations will be shown from a users perspective, but you can see the source code for the framework side in [docs/src/].

## Textual

[Textual] is a TUI (Text User Interface) framework for Python inspired by modern web development.

In this example, we add dependency injection functionality into Textual and use it to inject an HTTP client that pulls a markdown file from the web and displays it in the console.
This example mirrors [Textual's own simple.py example].

```Python
--8<-- "docs/src/textual/demo.py"
```

## Starlette

[Starlette] is a microframework with async support.

Adding dependency injection to Starlette is pretty straightforward.
We just need to bind the incoming requests.

```Python
--8<-- "docs/src/starlette/demo.py"
```

A full implementation would also need ways to extract bodies, headers, etc.
For an example of providing headers via dependency injection, see the [Dependants docs].

[docs/src/]: https://github.com/adriangb/di/tree/main/docs/src
[Textual's own simple.py example]: https://github.com/willmcgugan/textual/blob/main/examples/simple.py
[Textual]: https://github.com/willmcgugan/textual
[Starlette]: https://www.starlette.io
[Dependants docs]: dependants.md
