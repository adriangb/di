# Developer setup

This is a pure Python project and should be straightforward to set up on Linux or MacOS.
We do not support Windows for development, if you use Windows you'll have to use [VSCode DevContainers] or a similar solution.

We use [Poetry] for dependency management, and most of the config is the [pyproject.toml].

Linting is done via git hooks, managed by [pre-commit].
The linters may change over time, but they are configured in our [pre-commit-config.yaml].

Most of the setup and interaction with these systems is encapsulated in our [Makefile].

## Project setup

First, fork the repo and then clone your fork:

<div class="termy">

```console
$ git clone https://github.com/adriangb/di.git
---> 100%
$ cd di
```

</div>

Now install the project dependencies.
You will need [Make] installed along with a compatible Python version (currently, 3.9.X).

To set up the project, simply run:

<div class="termy">

```console
$ make init
```

</div>

This will create a `.venv` virtualenv that you can configure your IDE to use.

## Running tests

<div class="termy">

```console
$ make test
```

</div>

Tests are run with pytest, so you can also run them manually or configure your IDE to run them.
The tests are stored in the `tests/` directory.

## Running linting

Linting will run automatically on every commit.
To disable this, you can commit with `git commit --no-verify`.

You can also run linting manually:

<div class="termy">

```console
$ make lint
```

</div>

## Documentation

The docs are written as markdown and built with MkDocs.
Both the docs and their source code are stored in the `docs/` directory.

To preview the docs locally as you edit them, run

<div class="termy">

```console
$ make docs-serve
```

</div>

All of the code fragments in the docs are stored as `.py` files in `docs/src`.
These code fragments are tested as part of unit tests to ensure that the documentation stays up to date with the API.

## Releases

This project uses continious integration and continious delivery on a trunk based workflow.
Every merge into `main` should be fully functional code in a releasable state.
As part of your pull request, you should propose what type of change is being made and determine the right version bump appropriately.
While [conventional commits] are appreciated as a means of communication, especially for the merge commit, they are not *required* or enforced.
You are however required to bump the package version in [pyproject.toml].
Every commit into `main` needs a version bump so that a release can be made, even if it is a refactor or "chore" type change.

Once your change is merged, the new docs and PyPi package will be released automatically.
Every time a release is made on PyPi, a corresponding GitHub release will be created to correlate PyPi versions to git commits.

[make]: https://www.gnu.org/software/make/
[makefile]: https://github.com/adriangb/di/blob/main/Makefile
[poetry]: https://python-poetry.org/docs/master/
[pre-commit]: https://pre-commit.com
[pre-commit-config.yaml]: https://github.com/adriangb/di/blob/main/.pre-commit-config.yaml
[pyproject.toml]: https://github.com/adriangb/di/blob/main/pyproject.toml
[vscode devcontainers]: https://code.visualstudio.com/docs/remote/containers
[conventional commits]: https://www.conventionalcommits.org/en/v1.0.0/
