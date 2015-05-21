#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.


import six
from thr.utils import glob, regexp, diff
from thr.redis2http.counter import get_counter
import logging

logger = logging.getLogger("thr.redis2http.limits")


class Limits(object):

    limits = {}

    @classmethod
    def reset(cls):
        cls.limits = {}

    @classmethod
    def add(cls, name, limit):
        cls.limits[name] = limit

    @classmethod
    def check(cls, message):
        hashes = []
        computed_hashes = {}
        for name, limit in six.iteritems(cls.limits):
            hash_func = limit.hash_func
            if hash_func not in computed_hashes:
                computed_hashes[hash_func] = hash_func(message)
            hash = computed_hashes[hash_func]
            if hash is not None:
                if limit.check_hash(hash):
                    current_counter = get_counter(name)
                    if not limit.check_limit(current_counter):
                        logger.debug("Request refused, reason : %s failed "
                                     "to pass (%s > %s)", name,
                                     current_counter, limit.limit)
                        return None
                    hashes.append(name)
        logger.debug("Request accepted, updating the "
                     "following counters : %s", str(hashes))
        return hashes


class Limit(object):

    def __init__(self, hash_func, hash_value, limit):
        self.hash_func = hash_func
        self.hash_value = hash_value
        self.limit = limit

    def check_hash(self, hashed_message):
        if isinstance(self.hash_value, (glob, regexp, diff)):
            return self.hash_value.match(hashed_message)
        else:
            return self.hash_value == hashed_message

    def check_limit(self, value):
        return self.limit > value


def add_max_limit(name, hash_func, hash_value, max_limit):
    """
    Add a maximim limit for the specified value of the hash function

    Args:
        name: a limit name (unique)
        hash_func: a hash function
        hash_value: a string, :class:`~thr.http2redis.rules.glob` object
            or a compiled regular expression object
        max_limit: an int

    Examples:
        >>> def my_hash(message):
                return "toto"
        >>> add_max_limit("too_limit", my_hash, "toto", 3)
    """
    Limits.add(name, Limit(hash_func, hash_value, max_limit))
