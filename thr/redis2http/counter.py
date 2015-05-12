#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from collections import defaultdict


counters = defaultdict(int)


def get_counter(counter):
    global counters
    return counters[counter]


def set_counter(counter, value):
    global counters
    counters[counter] = value


def incr_counters(counter_list):
    global counters
    for counter in counter_list:
        counters[counter] += 1


def decr_counters(counter_list):
    global counters
    for counter in counter_list:
        counters[counter] -= 1


def del_counter(counter):
    global counters
    counters.pop(counter, None)
