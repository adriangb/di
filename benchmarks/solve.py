"""Profile solving a DAG

Run this file, then run:
snakeviz bench.prof
"""

import cProfile
import pstats
import timeit

import anyio

from benchmarks.utils import generate_dag
from di import Container, Dependant, Depends
from di.executors import ConcurrentAsyncExecutor, SimpleSyncExecutor


async def async_concurrent():
    container = Container(executor=ConcurrentAsyncExecutor())
    solved = container.solve(
        Dependant(generate_dag(Depends, 4, 3, 3, sync=False, sleep=(0, 0.01)))
    )
    profiler = cProfile.Profile()
    profiler.enable()
    await container.execute_async(solved)
    profiler.disable()
    stats = pstats.Stats(profiler)
    filename = "async_concurrent.prof"
    stats.dump_stats(filename=filename)
    print(f"Dumped cProfile stats to {filename}")
    start = timeit.default_timer()
    iters = 100
    for _ in range(iters):
        await container.execute_async(solved)
    elapsed = timeit.default_timer() - start
    print(f"{elapsed/iters:.2e} sec/iter")


def sync_sequential_large():
    container = Container(executor=SimpleSyncExecutor())
    solved = container.solve(
        Dependant(generate_dag(Depends, 4, 3, 3, sync=True, sleep=(0, 1e-5)))
    )
    profiler = cProfile.Profile()
    profiler.enable()
    container.execute_sync(solved)
    profiler.disable()
    stats = pstats.Stats(profiler)
    filename = "sync_sequential_large.prof"
    stats.dump_stats(filename=filename)
    print(f"Dumped cProfile stats to {filename}")
    start = timeit.default_timer()
    iters = 100
    for _ in range(iters):
        container.execute_sync(solved)
    elapsed = timeit.default_timer() - start
    print(f"{elapsed/iters:.2e} sec/iter")


def sync_sequential_small():
    container = Container(executor=SimpleSyncExecutor())
    solved = container.solve(
        Dependant(generate_dag(Depends, 1, 1, 1, sync=True, sleep=(0, 1e-5)))
    )
    profiler = cProfile.Profile()
    profiler.enable()
    container.execute_sync(solved)
    profiler.disable()
    stats = pstats.Stats(profiler)
    filename = "sync_sequential_small.prof"
    stats.dump_stats(filename=filename)
    print(f"Dumped cProfile stats to {filename}")
    start = timeit.default_timer()
    iters = 100
    for _ in range(iters):
        container.execute_sync(solved)
    elapsed = timeit.default_timer() - start
    print(f"{elapsed/iters:.2e} sec/iter")


if __name__ == "__main__":
    anyio.run(async_concurrent)
    sync_sequential_large()
    sync_sequential_small()
