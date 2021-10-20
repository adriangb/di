"""Profile solving a DAG

Run this file, then run:
snakeviz bench.prof
"""

import cProfile
import pstats
import timeit

from benchmarks.utils import generate_dag
from di import Container, Dependant, Depends
from di.executors import SimpleSyncExecutor

root = generate_dag(Depends, 1, 1, 1, sync=True)


def endpoint(dag: None = Depends(root)):
    return ...


container = Container(executor=SimpleSyncExecutor())
solved = container.solve(Dependant(endpoint))


def bench():
    container.execute_sync(solved)


def main():
    profiler = cProfile.Profile()
    profiler.enable()
    bench()
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.dump_stats(filename="bench.prof")
    print("Dumped cProfile stats to bench.prof")
    print(timeit.timeit("bench()", globals=globals(), number=10000))


if __name__ == "__main__":
    main()
