import functools
import inspect
import sys
from typing import Any, Callable, Dict, Mapping, Optional, Union

if sys.version_info < (3, 9):  # pragma: no cover
    from typing_extensions import Annotated, get_args, get_origin, get_type_hints
else:  # pragma: no cover
    from typing import Annotated, get_args, get_origin, get_type_hints

from di._utils.types import Some


def unwrap_callable(call: Any) -> Any:
    unwrapped = True
    while unwrapped:
        unwrapped = False
        if isinstance(call, functools.partial):
            call = call.func
            unwrapped = True
            continue
        if getattr(call, "__wrapped__", None):
            # maybe function wrapped with @wraps
            call = getattr(call, "__wrapped__")
            unwrapped = True
            continue
    return call


def is_coroutine_callable(call: Any) -> bool:
    if inspect.isclass(call):
        return False
    unwrapped_call = unwrap_callable(call)
    if inspect.iscoroutinefunction(unwrapped_call):
        return True
    dunder_call = getattr(unwrapped_call, "__call__", None)
    return inspect.iscoroutinefunction(dunder_call)


def is_async_gen_callable(call: Callable[..., Any]) -> bool:
    unwrapped_call = unwrap_callable(call)
    if inspect.isasyncgenfunction(unwrapped_call):
        return True
    dunder_call = getattr(unwrapped_call, "__call__", None)
    return inspect.isasyncgenfunction(dunder_call)


def is_gen_callable(call: Any) -> bool:
    unwrapped_call = unwrap_callable(call)
    if inspect.isgeneratorfunction(unwrapped_call):
        return True
    dunder_call = getattr(unwrapped_call, "__call__", None)
    return inspect.isgeneratorfunction(dunder_call)


def get_annotations(call: Callable[..., Any]) -> Dict[str, Any]:
    types_from: Callable[..., Any]
    if inspect.isclass(call):
        types_from = call.__init__
    elif is_callable_class(call):
        types_from = call.__call__  # type: ignore[operator] # mypy issue #5079
    else:
        types_from = call

    hints = get_type_hints(types_from, include_extras=True)
    hints = fix_annotated_optional_type_hints(hints)

    return hints


def is_callable_class(call: Callable[..., Any]) -> bool:
    function_or_method = inspect.isfunction(call) or inspect.ismethod(call)
    has_call = hasattr(call, "__call__")
    return not function_or_method and has_call


def fix_annotated_optional_type_hints(hints: Dict[str, Any]) -> Dict[str, Any]:
    """https://github.com/python/cpython/issues/90353"""
    for param_name, hint in hints.items():
        args = get_args(hint)
        if get_origin(hint) is Union and get_origin(next(iter(args))) is Annotated:
            hints[param_name] = next(iter(args))
    return hints


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


def get_type(param: inspect.Parameter) -> Optional[Some[Any]]:
    annotation = param.annotation
    if annotation is param.empty:
        return None
    if get_origin(annotation) is Annotated:
        annotation = next(iter(get_args(annotation)))
    return Some(annotation)
