import inspect
import types
from typing import Any, Callable, Dict, get_type_hints

from anydep.exceptions import WiringError


def is_async_context_manager(call: Callable) -> bool:
    return inspect.iscoroutinefunction(getattr(call, "__aenter__", None)) and inspect.iscoroutinefunction(
        getattr(call, "__aexit__", None)
    )


def is_context_manager(call: Callable) -> bool:
    return callable(getattr(call, "__enter__", None)) and callable(getattr(call, "__exit__", None))


def is_coroutine_callable(call: Callable) -> bool:
    if inspect.isroutine(call):
        return inspect.iscoroutinefunction(call)
    if inspect.isclass(call):
        return False
    call = getattr(call, "__call__", None)
    return inspect.iscoroutinefunction(call)


def is_async_gen_callable(call: Callable) -> bool:
    if inspect.isasyncgenfunction(call):
        return True
    call = getattr(call, "__call__", None)
    return inspect.isasyncgenfunction(call)


def is_gen_callable(call: Any) -> bool:
    if inspect.isgeneratorfunction(call):
        return True
    call = getattr(call, "__call__", None)
    return inspect.isgeneratorfunction(call)


def get_annotations(call: Callable) -> Dict[str, Any]:
    if inspect.isclass(call):
        types_from = call.__init__  # type: ignore
    elif not isinstance(call, types.FunctionType) and hasattr(call, "__call__"):
        # callable class
        types_from = call.__call__  # type: ignore
    else:
        types_from = call
    return get_type_hints(types_from)


def get_parameters(call: Callable) -> Dict[str, inspect.Parameter]:
    params = inspect.signature(call).parameters
    annotations = get_annotations(call)
    processed_params = {}
    for param_name, param in params.items():
        if isinstance(param.annotation, str):
            processed_params[param_name] = inspect.Parameter(
                name=param.name, kind=param.kind, default=param.default, annotation=annotations[param_name]
            )
        else:
            processed_params[param_name] = param

    return processed_params


def infer_call_from_annotation(parameter: inspect.Parameter) -> Callable:
    if parameter.annotation is None:
        raise WiringError(f"Unable to infer call for parameter {parameter.name}: no type annotation found")
    if not callable(parameter.annotation):
        raise WiringError(f"Annotation for {parameter.name} is not callable")
    return parameter.annotation
