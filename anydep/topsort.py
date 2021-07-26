#######################################################################
# Implements a topological sort algorithm.
#
# Copyright 2014 True Blade Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Notes:
#  Copied and modified from https://gitlab.com/ericvsmith/toposort to fix bugs
#
########################################################################

from functools import reduce
from typing import Dict, Generator, Set, TypeVar

__all__ = ["topsort", "CircularDependencyError"]


T = TypeVar("T")


class CircularDependencyError(ValueError):
    def __init__(self, message: str = None, *, data: Dict[T, Set[T]] = None):
        self.data = data
        if data is not None and message is None:
            # Sort the data just to make the output consistent, for use in
            #  error messages.  That's convenient for doctests.
            items = list(data.items())
            try:
                items = sorted(items)
            except TypeError:
                pass  # not sortable
            message = "Circular dependencies exist among these items: {{{}}}".format(
                ", ".join("{!r}:{!r}".format(key, value) for key, value in sorted(data.items()))
            )
        super().__init__(message)


def topsort(data: Dict[T, Set[T]]) -> Generator[Set[T], None, None]:
    """Dependencies are expressed as a dictionary whose keys are items
    and whose values are a set of dependent items. Output is a list of
    sets in topological order. The first set consists of items with no
    dependences, each subsequent set consists of items that depend upon
    items in the preceeding sets.
    """

    # Special case empty input.
    if len(data) == 0:
        return

    # Discard self-dependencies and copy two levels deep.
    data = {item: set(e for e in dep if e != item) for item, dep in data.items()}
    # Find all items that don't depend on anything.
    extra_items_in_deps = reduce(set.union, data.values()) - set(data.keys())
    # Add empty dependences where needed.
    data.update({item: set() for item in extra_items_in_deps})
    while True:
        ordered = set(item for item, dep in data.items() if len(dep) == 0)
        if not ordered:
            break
        yield ordered
        data = {item: (dep - ordered) for item, dep in data.items() if item not in ordered}
    if len(data) != 0:
        raise CircularDependencyError(data=data)
