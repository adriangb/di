import importlib.metadata as _importlib_metadata

__version__ = _importlib_metadata.version(__name__)


from di.container import Container
from di.dependency import Dependant, DependantProtocol
from di.params import Depends

__all__ = ("Container", "Dependant", "DependantProtocol", "Depends")
