"""Vendored copy of CPython's graphlib with the ability to clone an instance"""
from __future__ import annotations

from typing import Callable, Dict, Generator, Generic, Iterable, List, Mapping, Optional, Set, Tuple, TypeVar, Union, cast


_NODE_OUT = -1
_NODE_DONE = -2

T = TypeVar("T")


class CycleError(ValueError):
    pass



class PreparedState(Generic[T]):
    __slots__ = (
        "node2id", "id2node", "predecessor_counts", "successors", "ready_nodes", "npassedout", "nfinished"
    )
    node2id: Mapping[T, int]
    id2node: Tuple[T, ...]
    predecessor_counts: List[int]
    successors: Tuple[Tuple[int, ...], ...]
    ready_nodes: List[Tuple[int, T]]

    def __init__(
        self,
        node2id: Mapping[T, int],
        id2node: Tuple[T, ...],
        predecessor_counts: List[int],
        successors: Tuple[Tuple[int, ...], ...],
        ready_nodes: List[Tuple[int, T]],
    ) -> None:
        self.node2id = node2id
        self.id2node = id2node
        self.predecessor_counts = predecessor_counts
        self.successors = successors
        self.ready_nodes = ready_nodes
        self.npassedout = 0
        self.nfinished = 0

    def copy(self) -> PreparedState[T]:
        return PreparedState(
            node2id=self.node2id,
            id2node=self.id2node,
            predecessor_counts=self.predecessor_counts.copy(),
            successors=self.successors,
            ready_nodes=self.ready_nodes.copy(),
        )



class UnpreparedState(Generic[T]):
    __slots__ = ("node2id", "id2node", "predecessor_counts", "successors")
    node2id: Dict[T, int]
    id2node: List[T]
    predecessor_counts: List[int]
    successors: List[List[int]]

    def __init__(self) -> None:
        self.node2id = {}
        self.id2node = []
        self.predecessor_counts = []
        self.successors = []
    
    def get_nodeid(self, node: T) -> int:
        result = self.node2id.get(node, None)
        if result is None:
            self.node2id[node] = result = len(self.node2id)
            self.predecessor_counts.append(0)
            self.successors.append([])
            self.id2node.append(node)
        return result


class TopologicalSorter(Generic[T]):
    """Provides functionality to topologically sort a graph of hashable nodes"""
    __slots__ = ("_state", "_prepared")
    _state: Union[PreparedState[T], UnpreparedState[T]]

    def __init__(
        self,
        graph: Optional[ Mapping[T, Iterable[T]]] = None,
        *,
        state: Optional[Union[PreparedState[T], UnpreparedState[T]]] = None
    ) -> None:
        self._state = state or UnpreparedState()
        self._prepared = isinstance(self._state, PreparedState)
        if graph:
            for node, predecessors in graph.items():
                self.add(node, *predecessors)

    def add(self, node: T, *predecessors: T) -> None:
        if isinstance(self._state, PreparedState):
            raise ValueError("Nodes cannot be added after a call to prepare()")

        # Create the node -> predecessor edges
        nodeid = self._state.get_nodeid(node)
        self._state.predecessor_counts[nodeid] += len(predecessors)

        # Create the predecessor -> node edges
        for pred in predecessors:
            predid = self._state.get_nodeid(pred)
            self._state.successors[predid].append(nodeid)

    def prepare(self) -> None:
        if isinstance(self._state, PreparedState):
            raise ValueError("cannot prepare() more than once")

        ready_nodes = [
            (nid, self._state.id2node[nid])
            for nid, c in enumerate(self._state.predecessor_counts)
            if c == 0
        ]

        self._state = PreparedState(
            node2id=self._state.node2id,
            id2node=tuple(self._state.id2node),
            predecessor_counts=self._state.predecessor_counts,
            successors=tuple((tuple(suc) for suc in self._state.successors)),
            ready_nodes=ready_nodes,
        )
        self._prepared = True

        # self._state is set before we look for cycles on purpose:
        # if the user wants to catch the CycleError, that's fine,
        # they can continue using the instance to grab as many
        # nodes as possible before cycles block more progress
        cycle = self._find_cycle()
        if cycle:
            raise CycleError(f"nodes are in a cycle", cycle)

    def get_ready(self) -> Tuple[T, ...]:
        if not self._prepared:
            raise ValueError("prepare() must be called first")
        
        state = cast(PreparedState[T], self._state)

        # Get the nodes that are ready and mark them
        pc = state.predecessor_counts
        for nodeid, _ in state.ready_nodes:
            pc[nodeid] = _NODE_OUT

        # Clean the list of nodes that are ready and update
        # the counter of nodes that we have returned.
        state.npassedout += len(state.ready_nodes)
        res = tuple((node for _, node in state.ready_nodes))
        state.ready_nodes.clear()

        return res

    def is_active(self) -> bool:
        if isinstance(self._state, UnpreparedState):
            raise ValueError("prepare() must be called first")
        return self._state.nfinished < self._state.npassedout or bool(self._state.ready_nodes)

    def __bool__(self) -> bool:
        return self.is_active()

    def done(self, *nodes: T) -> None:
        if not self._prepared:
            raise ValueError("prepare() must be called first")
        
        state = cast(PreparedState[T], self._state)

        n2i = state.node2id
        i2n = state.id2node
        predecessor_counts = state.predecessor_counts
        successors = state.successors
        ready_nodes = state.ready_nodes

        for node in nodes:
            # Check if we know about this node (it was added previously using add()
            nid = n2i.get(node, None)
            if nid is None:
                raise ValueError(f"node {node!r} was not added using add()")

            # If the node has not being returned (marked as ready) previously, inform the user.
            stat = predecessor_counts[nid]
            if stat != _NODE_OUT:
                if stat >= 0:
                    raise ValueError(
                        f"node {node!r} was not passed out (still not ready)"
                    )
                elif stat == _NODE_DONE:
                    raise ValueError(f"node {node!r} was already marked done")
                else:
                    assert False, f"node {node!r}: unknown status {stat}"

            # Mark the node as processed
            predecessor_counts[nid] = _NODE_DONE

            # Go to all the successors and reduce the number of predecessors, collecting all the ones
            # that are ready to be returned in the next get_ready() call.
            for successorid in successors[nid]:
                npredecessors = predecessor_counts[successorid]
                predecessor_counts[successorid] = npredecessors - 1
                if npredecessors == 1:
                    ready_nodes.append((successorid, i2n[successorid]))
            state.nfinished += 1

    def _find_cycle(self) -> Optional[List[T]]:
        stack: List[T] = []
        itstack: List[Callable[[], T]] = []
        seen: Set[T] = set()
        node2stacki: Dict[T, int] = {}

        assert isinstance(self._state, PreparedState)

        n2i = self._state.node2id
        i2n = self._state.id2node
        successors = self._state.successors

        for node in self._state.node2id:
            if node in seen:
                continue

            while True:
                if node in seen:
                    # If we have seen already the node and is in the
                    # current stack we have found a cycle.
                    if node in node2stacki:
                        return stack[node2stacki[node] :] + [node]
                    # else go on to get next successor
                else:
                    seen.add(node)
                    it = (
                        i2n[s]
                        for s in successors[n2i[node]]
                    )
                    itstack.append(it.__next__)
                    node2stacki[node] = len(stack)
                    stack.append(node)

                # Backtrack to the topmost stack entry with
                # at least another successor.
                while stack:
                    try:
                        node = itstack[-1]()
                        break
                    except StopIteration:
                        del node2stacki[stack.pop()]
                        itstack.pop()
                else:
                    break
        return None

    def static_order(self) -> Generator[T, None, None]:
        self.prepare()
        while self.is_active():
            node_group = self.get_ready()
            yield from node_group
            self.done(*node_group)

    def copy(self) -> TopologicalSorter[T]:
        if isinstance(self._state, UnpreparedState):
            raise ValueError("prepare() must be called first")
        return TopologicalSorter(
            state=self._state.copy()
        )  # type: ignore[return-value]
