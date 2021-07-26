import inspect
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    asynccontextmanager,
    contextmanager,
)
from functools import partial
from typing import Dict, Optional, get_type_hints

import anyio

from anydep.cache import CachePolicy
from anydep.concurrency import contextmanager_in_threadpool, run_in_threadpool
from anydep.exceptions import WiringError
from anydep.inspect import is_async_gen_callable, is_coroutine_callable, is_gen_callable
from anydep.lifespan import DependencyLifespanPolicy
from anydep.models import Dependant, Dependency
from anydep.utils import call_from_annotation, order_of_execution


async def solve_dependant(
    *, solved: Dict[Dependant, Dependency], dependant: Dependant, lifespan: DependencyLifespanPolicy
) -> Dependency:
    args = (solved[arg] for arg in dependant.positional_arguments)
    kwargs = {keyword: solved[dep] for keyword, dep in dependant.keyword_arguments.items()}
    if is_async_gen_callable(dependant.call):  # type: ignore
        call = asynccontextmanager(partial(dependant.call, *args, **kwargs))  # type: ignore
    elif is_gen_callable(dependant.call):  # type: ignore
        call = contextmanager(partial(dependant.call, *args, **kwargs))  # type: ignore
    elif not is_coroutine_callable(dependant.call):  # type: ignore
        call = partial(run_in_threadpool, partial(dependant.call, *args, **kwargs))  # type: ignore
    else:
        call = partial(dependant.call, *args, **kwargs)  # type: ignore
    called = call()
    if isinstance(called, AbstractContextManager):
        called = contextmanager_in_threadpool(called)
    if isinstance(called, AbstractAsyncContextManager):
        res = await lifespan.bind_context(dependant=dependant, context_manager=called)  # type: ignore
    else:
        res = await called
    solved[dependant] = res
    return res


class Container:
    def wire_dependant(self, dependant: Dependant, *, cache: CachePolicy) -> None:
        if dependant.call is None:
            raise WiringError("Top level dependant must have a `call` attribute")
        for ((param_name, parameter), annotations) in zip(
            inspect.signature(dependant.call).parameters.items(),  # type: ignore
            get_type_hints(dependant.call).values(),
        ):
            if isinstance(parameter.default, Dependant):
                sub_dependant = parameter.default
                if sub_dependant.call is None:
                    sub_dependant.call = call_from_annotation(parameter, annotations)
            elif parameter.default is parameter.empty:
                sub_dependant = Dependant(call=call_from_annotation(parameter, annotations))
            else:
                continue  # use default value
            cached = cache.get(sub_dependant)
            if cached is None:
                self.wire_dependant(sub_dependant, cache=cache)
                cache[sub_dependant] = sub_dependant
                final = sub_dependant
            else:
                final = cached
            if parameter.POSITIONAL_ONLY:
                dependant.positional_arguments.append(final)
            else:
                dependant.keyword_arguments[param_name] = final

    async def solve(
        self,
        dependant: Dependant,
        *,
        solved: Optional[Dict[Dependant, Dependency]] = None,
        lifespan: Optional[DependencyLifespanPolicy] = None
    ) -> Dependency:
        solved = solved or {}
        for dep_group in order_of_execution(dependant):
            async with anyio.create_task_group() as tg:
                for dep in dep_group:
                    if dep in solved:
                        continue
                    target = partial(solve_dependant, solved=solved, lifespan=lifespan, dependant=dep)
                    tg.start_soon(target)
        return solved[dependant]
