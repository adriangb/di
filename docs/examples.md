# Examples

## Simple Example

Here is a simple example of how `di` works:

```python
--8<-- "docs_src/simple.py"
```

You will notice that `di` "auto-wired" `C`: we didn't have to tell it that `C` depends on `A` and `B`, or how to construct `A` and `B`, it was all inferred from type annotations.

In the [wiring] and [provider registration] chapters, you'll see how you can customize this behavior to tell `di` how to inject things like abstract interfaces or function return values.

## In-depth example

With this background in place, let's dive into a more in-depth example.

In this example, we'll look at what it would take for a web framework to provide dependency injection to its users via `di`.

Let's start by looking at the User's code.

```python hl_lines="20-30"
--8<-- "docs_src/web_framework.py"
```

As a user, you have very little boilerplate.
In fact, there is not a single line of code here that is not transmitting information.

Now let's look at the web framework side of things.
This part can get a bit complex, but it's okay because it's written once, in a library.

First, we'll need to create a `Container` instance.
This would be tied to the `App` or `Router` instance of the web framework.

```python hl_lines="11"
--8<-- "docs_src/web_framework.py"
```

Next, we "solve" the users' endpoint:

```python hl_lines="12"
--8<-- "docs_src/web_framework.py"
```

This should happen once, maybe at app startup.
The framework can then store the `solved` object, which contains all the information necessary to execute the dependency (dependency being in this case the user's endpoint/controller function).
This is very important for performance: we want to do the least amount of work possible for each incoming request.

Finally, we execute the endpoint for each incoming request:

```python hl_lines="13-16"
--8<-- "docs_src/web_framework.py"
```

When we do this, we provide the `Request` instance as a value.
This means that `di` does not introspect at all into the `Request` to figure out how to build it, it just hands the value off to anything that requests it.
You can also directly register providers, which is covered in the [provider registration] section of the docs.

You'll also notice the `executor` parameter.
As you'll see in the [architecture] chapter, one of the fundamental design principles in `di` is to decouple wiring, solving and execution.
This makes it trivial to, for example, enable concurrent execution of dependencies using threads, asynchronous task groups or any other execution paradigm you want.

[wiring]: wiring.md
[provider registration]: binds.md
