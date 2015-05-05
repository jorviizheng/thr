#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.


import six
import tornado
import uuid
from thr.utils import glob, regexp
import thr.redis2http.app


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
            cls.function_ids[hash_func] = uuid.uuid4()
        else:
            cls.limits[hash_func].append(limit)

    @classmethod
    @tornado.gen.coroutine
    def check(cls, message):
        hashes = []
        for hash_func, limits in six.iteritems(cls.limits):
            hash = hash_func(message)
            if hash:
                for limit in limits:
                    counter = cls.function_ids[hash_func]+'_'+limit.key
                    if limit.check_hash(hash):
                        current_workers = \
                            yield thr.redis2http.app.get_busy_workers(counter)
                        if not limit.check_limit(current_workers):
                            raise tornado.gen.Return(None)
                        hashes.append(counter)
        raise tornado.gen.Return(hashes)


class Limit(object):

    def __init__(self, hash, limit):
        self._hash = hash
        self._limit = limit

    @property
    def key(self):
        if isinstance(self._hash, six.string_types):
            return self._hash
        else:
            return self._hash.pattern

    def check_hash(self, hashed_message):
        if isinstance(self._hash, (glob, regexp)):
            return self._hash.match(hashed_message)
        else:
            return self._hash == hashed_message

    def check_limit(self, value):
        raise NotImplementedError


class MaxLimit(Limit):

    def check_limit(self, value):
        return self._limit > value


class MinRemainingLimit(Limit):

    def check_limit(self, value):
        return self._limit <= value


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
    Limits.add(hash_func, MaxLimit(hash_value, max_limit))


def add_min_remaining_limit(hash_func, hash_value, min_remaining_limit):
    """
    Add a minimum remaining limit for the specified value of the hash function

    Args:
        hash_func: a hash function
        hash_value: a string, :class:`~thr.http2redis.rules.glob` object
            or a compiled regular expression object
        min_remaining_limit: an int

    Examples:
        >>> def my_hash(message):
                return "toto"
        >>> add_min_remaining_limit(my_hash, "toto", 1)
    """
    Limits.add(hash_func, MinRemainingLimit(hash_value, min_remaining_limit))
