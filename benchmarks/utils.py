from random import Random
from typing import Any, Callable, Dict

random = Random(0)


def generate_dag(
    depends: Any,
    levels: int,
    nodes_per_level: int,
    dependencies_per_node: int,
    *,
    sync: bool = False,
) -> Callable[..., None]:
    """Build a complex DAG of async dependencies"""

    template = "def func_{}({}): ..." if sync else "async def func_{}({}): ..."

    funcs: Dict[str, Callable[..., Any]] = {}
    for level in range(levels):
        for node in range(nodes_per_level):
            name = f"{level}_{node}"
            deps = random.sample(
                list(funcs.keys()), k=min(len(funcs), dependencies_per_node)
            )
            params = ", ".join(
                [f"dep_{dep_name}: None = Depends({dep_name})" for dep_name in deps]
            )
            func_def = template.format(name, params)
            exec(func_def, {"Depends": depends}, funcs)
    name = "final"
    deps = list(funcs.keys())
    params = ", ".join(
        [f"dep_{dep_name}: None = Depends({dep_name})" for dep_name in deps]
    )
    func_def = template.format(name, params)
    exec(func_def, {"Depends": depends}, funcs)
    return funcs["func_final"]
