from __future__ import annotations

import copy
from collections import defaultdict, deque
from typing import DefaultDict, Deque, Dict, Generic, Hashable, Iterable, List, Mapping, MutableMapping, Sequence, TypeVar
import typing

from igraph import Graph

from di.exceptions import CircularDependencyError

T = TypeVar("T", bound=Hashable)


def comptue_dependant_counts(
    dag: Mapping[T, Iterable[T]],
) -> MutableMapping[T, int]:
    dependant_count: Dict[T, int] = dict.fromkeys(dag, 0)
    for subdeps in dag.values():
        for subdep in subdeps:
            dependant_count[subdep] += 1
    return dependant_count


def topsort(dag: Mapping[T, Iterable[T]]) -> List[T]:
    sorted: List[T] = []
    dependant_count = comptue_dependant_counts(dag)
    q: Deque[T] = deque([node for node in dag.keys() if dependant_count[node] == 0])
    while q:
        level = list(q)
        q.clear()
        for dependant in level:
            for dependency in dag[dependant]:
                try:
                    dependant_count[dependency] -= 1
                except KeyError:
                    raise CircularDependencyError
                if dependant_count[dependency] == 0:
                    dependant_count.pop(dependency)
                    q.append(dependency)
        for dependant in level:
            if dependant_count.pop(dependant, 0) == 0:
                dependant_count.pop(dependant, None)
        sorted.extend(level)
    for indegree in dependant_count.values():
        if indegree != 0:
            raise CircularDependencyError
    return sorted


class DAG(Generic[T]):

    _graph: Graph

    def __init__(self, dag: Mapping[T, Iterable[T]], root: T) -> None:
        self._root = root

        self.nodes: typing.Dict[str, T] = {}
        self.names: typing.Dict[T, str] = {}
        idxs: typing.Dict[T, int] = {}
        for idx, node in enumerate(dag.keys()):
            idxs[node] = idx
            name = str(idx)
            self.nodes[name] = node
            self.names[node] = name

        edge_list: typing.List[typing.Tuple[int, int]] = []
        for node, children in dag.items():
            for child in children:
                edge_list.append((idxs[node], idxs[child]))

        self._graph = Graph(
            n=len(dag),
            edges=edge_list,
            vertex_attrs={"name": list(dag.keys())},
            directed=True,
        )
    
    def _get_node_ids(self, items: Iterable[T]) -> List[int]:
        return list(self._graph.vs.select(name_in=set(items)))
    
    def copy(self) -> DAG[T]:
        new = copy.copy(self)
        new._graph = self._graph.copy()
        return new

    def remove_vertices(self, vertices: typing.Iterable[T]) -> None:
        self._graph.delete_vertices(self._get_node_ids(vertices))
        connected_vertices = self._graph.subcomponent(self._graph.vs.find(name=self._root).index, mode="out")
        self._graph = self._graph.induced_subgraph(connected_vertices)

    def get_dependency_counts(self) -> Dict[T, int]:
        items = self._graph.vs["name"]
        degrees = self._graph.outdegree()
        return dict(zip(items, degrees))

    def get_dependants(self) -> Mapping[T, Iterable[T]]:
        dependant_dag: Dict[T, Deque[T]] = {v["name"]: deque() for v in self._graph.vs}
        for edge in self._graph.es:
            source, dest = edge.tuple
            dependant_dag[self._graph.vs[dest]["name"]].append(self._graph.vs[source]["name"])
        return dependant_dag

    def get_leafs(self) -> Sequence[T]:
        return list(self._graph.vs.select(_outdegree=0)["name"])

    def topsort(self) -> List[T]:
        return list(self._graph.vs[self._graph.topological_sorting(mode="in")]["name"])