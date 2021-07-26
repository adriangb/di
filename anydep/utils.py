import inspect
from typing import Any, Callable

from anydep.exceptions import WiringError
from anydep.models import Dependency


def call_from_annotation(parameter: inspect.Parameter, annotation: Any) -> Callable[..., Dependency]:
    if annotation is None:
        raise WiringError(f"Unable to infer call for parameter {parameter.name}: no type annotation found")
    if not callable(annotation):
        raise WiringError(f"Annotation for {parameter.name} is not callable")
    return annotation
