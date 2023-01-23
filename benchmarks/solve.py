"""Run this file like python benchmarks/solve.py

It will print out results to the console and open web browser windows.
"""
import os

import anyio
from pyinstrument.profiler import Profiler  # type: ignore[import]

from benchmarks.utils import GraphSize, SleepTimes, generate_dag
from di import Container
from di.api.executor import SupportsAsyncExecutor, SupportsSyncExecutor
from di.dependent import Dependent
from di.executors import AsyncExecutor, ConcurrentAsyncExecutor, SyncExecutor

INTERVAL = 10e-6  # 10 us


async def async_bench(
    sleep: SleepTimes,
    graph: GraphSize,
    executor: SupportsAsyncExecutor,
    iters: int,
    name: str,
) -> None:
    container = Container()
    solved = container.solve(
        Dependent(generate_dag(graph, sync=False, sleep=sleep)), scopes=[None]
    )
    p = Profiler()
    async with container.enter_scope(None) as state:
        await solved.execute_async(executor=executor, state=state)
    p.start()
    for _ in range(iters):
        async with container.enter_scope(None) as state:
            await solved.execute_async(executor=executor, state=state)
    p.stop()
    p.print()
    with open(f"bench_html/{name}.html", mode="w") as f:
        f.write(p.output_html())


def sync_bench(
    sleep: SleepTimes,
    graph: GraphSize,
    executor: SupportsSyncExecutor,
    iters: int,
    name: str,
) -> None:
    container = Container()
    solved = container.solve(
        Dependent(generate_dag(graph, sync=True, sleep=sleep)), scopes=[None]
    )
    executor = SyncExecutor()
    p = Profiler()
    with container.enter_scope(None) as state:
        solved.execute_sync(executor=executor, state=state)
    p.start()
    for _ in range(iters):
        with container.enter_scope(None) as state:
            solved.execute_sync(executor=executor, state=state)
    p.stop()
    p.print()
    with open(f"bench_html/{name}.html", mode="w") as f:
        f.write(p.output_html())


LARGE_GRAPH = GraphSize(25, 5, 5)
SMALL_GRAPH = GraphSize(1, 1, 1)
FAST_DEPS = SleepTimes(0, 0)
SLOW_DEPS = SleepTimes(1e-3, 1e-3)


if __name__ == "__main__":
    if not os.path.exists("bench_html"):
        os.mkdir("bench_html")
    anyio.run(
        async_bench,
        FAST_DEPS,
        SMALL_GRAPH,
        AsyncExecutor(),
        5_000,
        "async-fast_deps-small_graph",
    )
    anyio.run(
        async_bench,
        FAST_DEPS,
        LARGE_GRAPH,
        AsyncExecutor(),
        5_000,
        "async-fast_deps-large_graph",
    )
    anyio.run(
        async_bench,
        SLOW_DEPS,
        SMALL_GRAPH,
        ConcurrentAsyncExecutor(),
        5_000,
        "async-slow_deps-small_graph",
    )
    anyio.run(
        async_bench,
        SLOW_DEPS,
        LARGE_GRAPH,
        ConcurrentAsyncExecutor(),
        5_000,
        "async-slow_deps-large_graph",
    )
    sync_bench(
        FAST_DEPS,
        SMALL_GRAPH,
        SyncExecutor(),
        iters=5_000,
        name="sync-fast_deps-small_graph",
    )
    sync_bench(
        FAST_DEPS,
        LARGE_GRAPH,
        SyncExecutor(),
        iters=5_000,
        name="sync-fast_deps-large_graph",
    )
    sync_bench(
        SLOW_DEPS,
        SMALL_GRAPH,
        SyncExecutor(),
        iters=5_000,
        name="sync-slow_deps-small_graph",
    )
    sync_bench(
        SLOW_DEPS,
        LARGE_GRAPH,
        SyncExecutor(),
        iters=5_000,
        name="sync-slow_deps-large_graph",
    )
