"""Profile solving a DAG

Run this file, then run:
snakeviz bench.prof
"""

import cProfile
import pstats

from benchmarks.utils import generate_dag
from di import Container, Dependant, Depends

root = generate_dag(Depends, 1, 1, 1)


async def endpoint(dag: None = Depends(root)):
    return ...


container = Container()
solved = container.solve(Dependant(endpoint))


async def bench():
    await container.execute_async(solved)


async def main():
    profiler = cProfile.Profile()
    profiler.enable()
    await bench()
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.dump_stats(filename="bench.prof")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
