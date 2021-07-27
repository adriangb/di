import inspect
from typing import Any, Callable, List, get_type_hints

from anydep.exceptions import WiringError
from anydep.models import Dependency, DependencyProvider, Parameter


def is_coroutine_callable(call: Callable[..., Any]) -> bool:
    if inspect.isroutine(call):
        return inspect.iscoroutinefunction(call)
    if inspect.isclass(call):
        return False
    call = getattr(call, "__call__", None)
    return inspect.iscoroutinefunction(call)


def is_async_gen_callable(call: Callable[..., Any]) -> bool:
    if inspect.isasyncgenfunction(call):
        return True
    call = getattr(call, "__call__", None)
    return inspect.isasyncgenfunction(call)


def is_gen_callable(call: Callable[..., Any]) -> bool:
    if inspect.isgeneratorfunction(call):
        return True
    call = getattr(call, "__call__", None)
    return inspect.isgeneratorfunction(call)


def get_parameters(call: DependencyProvider) -> List[Parameter]:
    res = []
    params = inspect.signature(call).parameters  # type: ignore
    if inspect.isclass(call):
        types_from = call.__init__  # type: ignore
    else:
        types_from = call
    annotations = get_type_hints(types_from)  # type: ignore
    for param_name, parameter in params.items():
        res.append(
            Parameter(
                positional=parameter.kind == inspect.Parameter.POSITIONAL_ONLY,
                name=parameter.name,
                default=parameter.default,
                annotation=annotations.get(param_name, None),
            )
        )
    return res


def call_from_annotation(parameter: Parameter) -> Callable[..., Dependency]:
    if parameter.annotation is None:
        raise WiringError(f"Unable to infer call for parameter {parameter.name}: no type annotation found")
    if not callable(parameter.annotation):
        raise WiringError(f"Annotation for {parameter.name} is not callable")
    return parameter.annotation
