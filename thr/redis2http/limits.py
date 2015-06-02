#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.


import six
from thr.utils import glob, regexp, diff
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
    def conditions(cls, message):
        conditions = []
        computed_hashes = {}
        for name, limit in six.iteritems(cls.limits):
            hash_func = limit.hash_func
            if hash_func not in computed_hashes:
                computed_hashes[hash_func] = hash_func(message)
            hash = computed_hashes[hash_func]
            if hash is not None:
                if limit.check_hash(hash):
                    counter = "%s%s" % (name, limit.counter_suffix(hash))
                    conditions.append((counter, limit.limit))
        return conditions


class Limit(object):

    def __init__(self, hash_func, hash_value, limit, show_in_stats=True):
        if callable(hash_value):
            if hash_value != hash_func:
                raise Exception("hash_value is callable and not hash_func")
        self.hash_func = hash_func
        self.hash_value = hash_value
        self.limit = limit
        self.show_in_stats = show_in_stats

    def counter_suffix(self, hashed_message):
        if self.hash_value == self.hash_func:
            return "==%s" % hashed_message
        else:
            return ""

    def check_hash(self, hashed_message):
        if '==' in hashed_message:
            raise Exception("'==' not allowed in hashed_message")
        if self.hash_func == self.hash_value:
            return True
        if isinstance(self.hash_value, (glob, regexp, diff)):
            return self.hash_value.match(hashed_message)
        else:
            return self.hash_value == hashed_message

    def check_limit(self, value):
        return self.limit > value


def add_max_limit(name, hash_func, hash_value, max_limit,
                  show_in_stats=True):
    """
    Add a maximim limit for the specified value of the hash function

    Args:
        name: a limit name (unique)
        hash_func: a hash function
        hash_value: a string, :class:`~thr.http2redis.rules.glob` object
            or a compiled regular expression object
        max_limit: an int
        show_in_stats: a boolean to hide (False) some limits from
            counter stats (if too many values).

    Examples:
        >>> def my_hash(message):
                return "toto"
        >>> add_max_limit("too_limit", my_hash, "toto", 3)
    """
    if "==" in name:
        raise Exception("'==' not allowed in limit names")
    Limits.add(name, Limit(hash_func, hash_value, max_limit, show_in_stats))
