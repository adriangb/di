#######################################################################
# Tests for topsort module.
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
#   Copied and modified from https://gitlab.com/ericvsmith/toposort
#
########################################################################

import unittest

from anydep.topsort import CircularDependencyError, topsort


class TestCase(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(
            list(
                topsort(
                    {
                        2: {11},
                        9: {11, 8},
                        10: {11, 3},
                        11: {7, 5},
                        8: {7, 3},
                    }
                )
            ),
            [
                {3, 5, 7},
                {8, 11},
                {2, 9, 10},
            ],
        )

        # make sure self dependencies are ignored
        self.assertEqual(
            list(
                topsort(
                    {
                        2: {2, 11},
                        9: {11, 8},
                        10: {10, 11, 3},
                        11: {7, 5},
                        8: {7, 3},
                    }
                )
            ),
            [
                {3, 5, 7},
                {8, 11},
                {2, 9, 10},
            ],
        )

        self.assertEqual(list(topsort({1: set()})), [{1}])
        self.assertEqual(list(topsort({1: {1}})), [{1}])

    def test_no_dependencies(self):
        self.assertEqual(
            list(
                topsort(
                    {
                        1: {2},
                        3: {4},
                        5: {6},
                    }
                )
            ),
            [{2, 4, 6}, {1, 3, 5}],
        )

        self.assertEqual(
            list(
                topsort(
                    {
                        1: set(),
                        3: set(),
                        5: set(),
                    }
                )
            ),
            [{1, 3, 5}],
        )

    def test_empty(self):
        self.assertEqual(list(topsort({})), [])

    def test_strings(self):
        self.assertEqual(
            list(
                topsort(
                    {
                        "2": {"11"},
                        "9": {"11", "8"},
                        "10": {"11", "3"},
                        "11": {"7", "5"},
                        "8": {"7", "3"},
                    }
                )
            ),
            [
                {"3", "5", "7"},
                {"8", "11"},
                {"2", "9", "10"},
            ],
        )

    def test_objects(self):
        o2 = object()
        o3 = object()
        o5 = object()
        o7 = object()
        o8 = object()
        o9 = object()
        o10 = object()
        o11 = object()
        self.assertEqual(
            list(
                topsort(
                    {
                        o2: {o11},
                        o9: {o11, o8},
                        o10: {o11, o3},
                        o11: {o7, o5},
                        o8: {o7, o3, o8},
                    }
                )
            ),
            [
                {o3, o5, o7},
                {o8, o11},
                {o2, o9, o10},
            ],
        )

    def test_cycle(self):
        # a simple, 2 element cycle
        # make sure we can catch this both as ValueError and CircularDependencyError
        self.assertRaises(ValueError, list, topsort({1: {2}, 2: {1}}))
        with self.assertRaises(CircularDependencyError) as ex:
            list(topsort({1: {2}, 2: {1}}))
        self.assertEqual(ex.exception.data, {1: {2}, 2: {1}})

        # an indirect cycle
        self.assertRaises(
            ValueError,
            list,
            topsort(
                {
                    1: {2},
                    2: {3},
                    3: {1},
                }
            ),
        )
        with self.assertRaises(CircularDependencyError) as ex:
            list(
                topsort(
                    {
                        1: {2},
                        2: {3},
                        3: {1},
                    }
                )
            )
        self.assertEqual(ex.exception.data, {1: {2}, 2: {3}, 3: {1}})

        # not all elements involved in a cycle
        with self.assertRaises(CircularDependencyError) as ex:
            list(
                topsort(
                    {
                        1: {2},
                        2: {3},
                        3: {1},
                        5: {4},
                        4: {6},
                    }
                )
            )
        self.assertEqual(ex.exception.data, {1: set([2]), 2: set([3]), 3: set([1])})

    def test_input_not_modified(self):
        def get_data():
            return {
                2: {11},
                9: {11, 8},
                10: {11, 3},
                11: {7, 5},
                8: {7, 3, 8},  # includes something self-referential
            }

        data = get_data()
        orig = get_data()
        self.assertEqual(data, orig)
        self.assertEqual(data, orig)

    def test_input_not_modified_when_cycle_error(self):
        def get_data():
            return {
                1: {2},
                2: {1},
                3: {4},
            }

        data = get_data()
        orig = get_data()
        self.assertEqual(data, orig)
        self.assertRaises(ValueError, list, topsort(data))
        self.assertEqual(data, orig)
