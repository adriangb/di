from functools import cached_property
from inspect import Parameter
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Generic,
    Hashable,
    Optional,
    TypeVar,
    Union,
)

from anydep.exceptions import WiringError
from anydep.inspect import get_parameters, infer_call_from_annotation

DependencyType = TypeVar("DependencyType")


CallableProvider = Callable[..., DependencyType]
CoroutineProvider = Callable[..., Awaitable[DependencyType]]
GeneratorProvider = Callable[..., Generator[DependencyType, None, None]]
AsyncGeneratorProvider = Callable[..., AsyncGenerator[DependencyType, None]]

DependencyProviderType = Union[
    CallableProvider[DependencyType],
    CoroutineProvider[DependencyType],
    GeneratorProvider[DependencyType],
    AsyncGeneratorProvider[DependencyType],
]

Scope = Hashable

Dependency = Any

DependencyProvider = DependencyProviderType[Dependency]


class Dependant(Generic[DependencyType]):
    def __init__(
        self,
        call: Optional[DependencyProviderType[DependencyType]] = None,
        scope: Optional[Scope] = None,
        **kwargs: Any,
    ) -> None:
        self.call = call
        self.scope = scope
        vars(self).update(kwargs)

    def __hash__(self) -> int:
        return id(self)

    @cached_property
    def parameters(self) -> Dict[str, Parameter]:
        return self.gather_parameters()

    @cached_property
    def dependencies(self) -> Dict[str, "Dependant[DependencyProvider]"]:
        return self.gather_dependencies()

    def gather_parameters(self) -> Dict[str, Parameter]:
        assert self.call is not None, "Cannot gather parameters without a bound call"
        return get_parameters(self.call)

    def gather_dependencies(self) -> Dict[str, "Dependant[DependencyProvider]"]:
        res = {}
        for param_name, param in self.parameters.items():
            if isinstance(param.default, Dependant):
                sub_dependant = param.default
                if sub_dependant.call is None:
                    sub_dependant.call = sub_dependant.infer_call_from_annotation(param)
            elif param.default is param.empty:
                sub_dependant = self.__class__(call=self.infer_call_from_annotation(param))
            else:
                continue  # use default value
            res[param_name] = sub_dependant
        return res

    def infer_call_from_annotation(self, param: Parameter) -> DependencyProvider:
        if param.annotation is param.empty:
            raise WiringError("Cannot wire a parameter with no default and no type annotation")
        return infer_call_from_annotation(param)
