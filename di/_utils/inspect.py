import functools
import inspect
import sys
from functools import lru_cache, wraps
from typing import Any, Callable, Dict, Mapping, Union

if sys.version_info < (3, 9):
    from typing_extensions import Annotated, get_args, get_origin, get_type_hints
else:
    from typing import Annotated, get_type_hints, get_origin, get_args

from di.exceptions import WiringError


def cached_accept_callable_class(
    maxsize: int,
) -> Callable[[Callable[..., bool]], Callable[..., bool]]:
    def wrapper(func: Callable[..., bool]) -> Callable[..., bool]:
        func = lru_cache(maxsize=maxsize)(func)

        @wraps(func)
        def inner(call: Any) -> bool:
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

        return inner

    return wrapper


@cached_accept_callable_class(maxsize=2 ** 10)
def is_coroutine_callable(call: Callable[..., Any]) -> bool:
    return inspect.iscoroutinefunction(call)


@cached_accept_callable_class(maxsize=2 ** 10)
def is_async_gen_callable(call: Callable[..., Any]) -> bool:
    return inspect.isasyncgenfunction(call)


@cached_accept_callable_class(maxsize=2 ** 10)
def is_gen_callable(call: Any) -> bool:
    return inspect.isgeneratorfunction(call)


@lru_cache(maxsize=2 ** 10)
def get_annotations(call: Callable[..., Any]) -> Dict[str, Any]:
    types_from: Callable[..., Any]
    if not (
        inspect.isclass(call) or inspect.isfunction(call) or inspect.ismethod(call)
    ) and hasattr(call, "__call__"):
        # callable class
        types_from = call.__call__  # type: ignore[misc,operator] # accessing __init__ directly
    else:
        # method
        types_from = call
    hints = get_type_hints(types_from, include_extras=True)
    # for no apparent reason, Annotated[Optional[T]] comes back as Optional[Annotated[Optional[T]]]
    # so remove the outer Optional if this is the case
    for param_name, hint in hints.items():
        args = get_args(hint)
        if get_origin(hint) is Union and get_origin(next(iter(args))) is Annotated:
            hints[param_name] = next(iter(args))
    return hints


@lru_cache(maxsize=2 ** 10)
def get_parameters(call: Callable[..., Any]) -> Dict[str, inspect.Parameter]:
    params: Mapping[str, inspect.Parameter]
    if inspect.isclass(call) and (call.__new__ is not object.__new__):  # type: ignore[comparison-overlap]
        # classes overriding __new__, including some generic metaclasses, result in __new__ getting read
        # instead of __init__
        params = inspect.signature(call.__init__).parameters  # type: ignore[misc] # accessing __init__ directly
        params = dict(params)
        params.pop(next(iter(params.keys())))  # first parameter to __init__ is self
    else:
        params = inspect.signature(call).parameters
    annotations = get_annotations(call)
    processed_params: Dict[str, inspect.Parameter] = {}
    for param_name, param in params.items():
        param = param.replace(annotation=annotations.get(param_name, param.annotation))
        processed_params[param_name] = param
    return processed_params


def infer_call_from_annotation(parameter: inspect.Parameter) -> Callable[..., Any]:
    if not callable(parameter.annotation):
        raise WiringError(
            f"Annotation for {parameter.name} is not a callable class or function and so we cannot autowire it."
            " You must explicity provide a default value implementing the DependantBase"
        )
    return parameter.annotation  # type: ignore[no-any-return]
