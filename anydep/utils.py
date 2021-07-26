import inspect
from typing import Any, Callable, Dict, Generator, Set

from toposort import toposort  # type: ignore

from anydep.exceptions import WiringError
from anydep.models import Dependant, Dependency


def call_from_annotation(parameter: inspect.Parameter, annotation: Any) -> Callable[..., Dependency]:
    if annotation is None:
        raise WiringError(f"Unable to infer call for parameter {parameter.name}: no type annotation found")
    if not callable(annotation):
        raise WiringError(f"Annotation for {parameter.name} is not callable")
    return annotation


def get_flat_dependencies(dependant: Dependant) -> Set[Dependant]:
    if dependant.wired:
        raise ValueError("Dependant must be wired")
    dependencies = set()
    for sub_dependant in dependant.dependencies:
        dependencies.update(get_flat_dependencies(sub_dependant))
    return dependencies


def order_of_execution(dependant: Dependant) -> Generator[Set[Dependant], None, None]:
    graph: Dict[Dependant, Set[Dependant]] = {}

    def build_graph(dep: Dependant) -> None:
        if dep.dependencies is None:
            raise ValueError("Dependant must be wired")
        if dep not in graph:
            graph[dep] = set()
        for sub_dep in dep.dependencies:
            graph[dep].add(sub_dep)
            build_graph(sub_dep)

    build_graph(dependant)
    return toposort(graph)
