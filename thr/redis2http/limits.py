#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.


import six
import uuid
from thr.utils import glob, regexp, diff
from thr.redis2http.counter import get_counter
import logging

logger = logging.getLogger("thr.redis2http.limits")


class Limits(object):

    limits = {}
    function_ids = {}

    @classmethod
    def reset(cls):
        cls.limits = {}

    @classmethod
    def add(cls, hash_func, limit):
        if hash_func not in cls.limits:
            cls.limits[hash_func] = [limit]
            cls.function_ids[hash_func] = str(uuid.uuid4())
        else:
            cls.limits[hash_func].append(limit)

    @classmethod
    def check(cls, message):
        hashes = []
        for hash_func, limits in six.iteritems(cls.limits):
            hash = hash_func(message)
            if hash:
                for limit in limits:
                    counter = cls.function_ids[hash_func]+'_'+limit.key
                    if limit.check_hash(hash):
                        current_workers = get_counter(counter)
                        if not limit.check_limit(current_workers):
                            logger.info("Request refused, reason : %s failed "
                                        "to pass %s (%s > %s)", hash,
                                        limit.key, current_workers,
                                        limit._limit)
                            return None
                        hashes.append(counter)
        logger.info("Request accepted, updating the "
                    "following counters : %s", str(hashes))
        return hashes


class Limit(object):

    def __init__(self, hash, limit):
        self._hash = hash
        self._limit = limit

    @property
    def key(self):
        if isinstance(self._hash, six.string_types):
            return self._hash
        else:
            return str(self._hash)

    def check_hash(self, hashed_message):
        if isinstance(self._hash, (glob, regexp, diff)):
            return self._hash.match(hashed_message)
        else:
            return self._hash == hashed_message

    def check_limit(self, value):
        return self._limit > value


def add_max_limit(hash_func, hash_value, max_limit):
    """
    Add a maximim limit for the specified value of the hash function

    Args:
        hash_func: a hash function
        hash_value: a string, :class:`~thr.http2redis.rules.glob` object
            or a compiled regular expression object
        max_limit: an int

    Examples:
        >>> def my_hash(message):
                return "toto"
        >>> add_max_limit(my_hash, "toto", 3)
    """
    Limits.add(hash_func, Limit(hash_value, max_limit))
