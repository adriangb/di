import inspect
import types
from dataclasses import dataclass
from functools import lru_cache
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Dict,
    Generator,
    Generic,
    Mapping,
    Protocol,
    TypeVar,
    Union,
    cast,
    get_type_hints,
)

from di.exceptions import WiringError

CallableProvider = Callable[..., Any]
CoroutineProvider = Callable[..., Coroutine[Any, Any, Any]]
GeneratorProvider = Callable[..., Generator[Any, None, None]]
AsyncGeneratorProvider = Callable[..., AsyncGenerator[Any, None]]

DependencyProvider = Union[
    AsyncGeneratorProvider,
    CoroutineProvider,
    GeneratorProvider,
    CallableProvider,
]


T = TypeVar("T")


VARIABLE_ARGS = (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)


# this should be a NamedTuple
# but https://github.com/python/mypy/issues/685
# we need the generic type
# so we can use it for DependantProtocol and Task
@dataclass
class DependencyParameter(Generic[T]):
    dependency: T
    parameter: inspect.Parameter


@lru_cache(maxsize=4096)
def is_coroutine_callable(call: DependencyProvider) -> bool:
    if inspect.isroutine(call):
        return inspect.iscoroutinefunction(call)
    if inspect.isclass(call):
        return False
    return inspect.iscoroutinefunction(getattr(call, "__call__", None))


@lru_cache(maxsize=4096)
def is_async_gen_callable(call: DependencyProvider) -> bool:
    if inspect.isasyncgenfunction(call):
        return True
    return inspect.isasyncgenfunction(getattr(call, "__call__", None))


@lru_cache(maxsize=4096)
def is_gen_callable(call: Any) -> bool:
    if inspect.isgeneratorfunction(call):
        return True
    call = getattr(call, "__call__", None)
    return inspect.isgeneratorfunction(call)


@lru_cache(maxsize=1024)
def get_annotations(call: DependencyProvider) -> Dict[str, Any]:
    types_from: DependencyProvider
    if inspect.isclass(call):
        types_from = call.__init__  # type: ignore
    elif not isinstance(call, types.FunctionType) and hasattr(call, "__call__"):
        # callable class
        types_from = call.__call__  # type: ignore
    else:
        types_from = call
    return get_type_hints(types_from)


@lru_cache(maxsize=1024)
def get_parameters(call: DependencyProvider) -> Dict[str, inspect.Parameter]:
    params: Mapping[str, inspect.Parameter]
    if (
        inspect.isclass(call)
        and hasattr(call, "__new__")
        and call.__new__ is not object.__new__
        and hasattr(call, "__init__")
    ):
        # classes overriding __new__, including some generic metaclasses, result in __new__ getting read
        # instead of __init__
        params = inspect.signature(call.__init__).parameters  # type: ignore
        params = dict(params)
        params.pop(next(iter(params.keys())))  # first parameter to __init__ is self
    else:
        params = inspect.signature(call).parameters
    annotations = get_annotations(call)
    processed_params: Dict[str, inspect.Parameter] = {}
    for param_name, param in params.items():
        if param.kind in VARIABLE_ARGS and type(call) is type(Protocol):
            # protocol __init__'s come with *args and **kwargs for error handling
            # but these are fake: protocols can't be instantiated anyway
            continue  # pragma: no cover
        processed_params[param_name] = inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=annotations.get(param_name, param.annotation),
        )

    return processed_params


@lru_cache(maxsize=1024)
def infer_call_from_annotation(parameter: inspect.Parameter) -> DependencyProvider:
    if not (
        callable(parameter.annotation)
        and (
            inspect.isclass(parameter.annotation)
            or inspect.isfunction(parameter.annotation)
        )
    ):
        raise WiringError(
            f"Annotation for {parameter.name} is not a callable class or function and so we cannot autowire it."
            " You must explicity provide a default value implementing the DependencyProtocol"
        )
    return cast(DependencyProvider, parameter.annotation)
