#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from collections import defaultdict


counters = defaultdict(int)
counters_blocks = defaultdict(int)


def get_counter(counter):
    return counters[counter]


def set_counter(counter, value):
    global counters
    counters[counter] = value


def incr_counters(counter_list):
    global counters
    for counter in counter_list:
        counters[counter] += 1


def get_counter_blocks(counter):
    return counters_blocks[counter]


def conditional_incr_counters(conditions):
    global counters, counters_blocks
    blocked_counters = []
    for counter_name, limit in conditions:
        if limit <= counters[counter_name]:
            blocked_counters.append(counter_name)
            counters_blocks[counter_name] += 1
    if len(blocked_counters) == 0:
        tmp = [x[0] for x in conditions]
        incr_counters(tmp)
        return (True, tmp)
    else:
        return (False, blocked_counters)


def decr_counters(counter_list):
    global counters
    for counter in counter_list:
        counters[counter] -= 1
        if counters[counter] == 0:
            # to avoir some memory leaks
            del(counters[counter])


def del_counter(counter):
    global counters
    counters.pop(counter, None)
