import functools
import inspect
from functools import lru_cache, wraps
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Dict,
    Generator,
    Mapping,
    Optional,
    TypeVar,
    Union,
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


def cached_accept_callable_class(
    maxsize: int,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def wrapper(func: Callable[..., T]) -> Callable[..., T]:
        func = lru_cache(maxsize=maxsize)(func)

        @wraps(func)
        def inner(call: Any):
            if not callable(call):
                return False
            if inspect.isclass(call):
                return False
            if isinstance(call, functools.partial):
                call = call.func
            if func(call):
                return True
            _call = getattr(call, "__call__", None)
            if _call is None:
                return False
            return func(_call)

        return inner  # type: ignore[return-value]

    return wrapper


@cached_accept_callable_class(maxsize=2048)
def is_coroutine_callable(call: DependencyProvider) -> bool:
    return inspect.iscoroutinefunction(call)


@cached_accept_callable_class(maxsize=2048)
def is_async_gen_callable(call: DependencyProvider) -> bool:
    return inspect.isasyncgenfunction(call)


@cached_accept_callable_class(maxsize=2048)
def is_gen_callable(call: Any) -> bool:
    return inspect.isgeneratorfunction(call)


@lru_cache(maxsize=2048)
def get_annotations(call: DependencyProvider) -> Dict[str, Any]:
    types_from: DependencyProvider
    if inspect.isclass(call):
        types_from = call.__init__  # type: ignore[misc] # accessing __init__ directly
    elif not (inspect.isfunction(call) or inspect.ismethod(call)) and hasattr(
        call, "__call__"
    ):
        # callable class
        types_from = call.__call__  # type: ignore[misc,operator] # accessing __init__ directly
    else:
        # method
        types_from = call
    return get_type_hints(types_from)


@lru_cache(maxsize=2048)
def get_parameters(call: DependencyProvider) -> Dict[str, inspect.Parameter]:
    params: Mapping[str, inspect.Parameter]
    if inspect.isclass(call) and call.__new__ is not object.__new__:
        # classes overriding __new__, including some generic metaclasses, result in __new__ getting read
        # instead of __init__
        params = inspect.signature(call.__init__).parameters  # type: ignore[misc] # accessing __init__ directly
        params = dict(params)
        params.pop(next(iter(params.keys())))  # first parameter to __init__ is self
    else:
        params = inspect.signature(call).parameters
    annotations: Optional[Dict[str, Any]] = None
    processed_params: Dict[str, inspect.Parameter] = {}
    for param_name, param in params.items():
        if isinstance(param.annotation, str):
            if annotations is None:
                annotations = get_annotations(call)
            param = param.replace(
                annotation=annotations.get(param_name, param.annotation)
            )
        processed_params[param_name] = param
    return processed_params


def infer_call_from_annotation(parameter: inspect.Parameter) -> DependencyProvider:
    if not callable(parameter.annotation):
        raise WiringError(
            f"Annotation for {parameter.name} is not a callable class or function and so we cannot autowire it."
            " You must explicity provide a default value implementing the DependencyProtocol"
        )
    return parameter.annotation
