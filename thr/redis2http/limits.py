#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.


from utils import glob


class Hashes(object):

    hashes = []

    @classmethod
    def add_hash(cls, hash_func, limits):
        cls.hashes.append(Limits(hash_func, limits))

    @classmethod
    def get_hashes(cls, message):
        return [limit.get_hash(message) for limit in cls.hashes]


class Limits(object):

    def __init__(self, hash_func, limits=[]):
        self._hash_func = hash_func
        self._limits = limits

    def get_hash(self, message):
        return self._hash_func(message)

    def add_limit(self, limit):
        self._limits.append(limit)

    def check(self, message, value):
        hash = self._hash_func(message)
        for limit in self._limits:
            if not limit.check(hash, value):
                return False
        return True


class Limit(object):

    def __init__(self, hash, limit):
        self._hash = hash
        self._limit = limit

    def check_hash(self, hashed_message):
        if isinstance(self._hash, (glob, RegexpType)):
            return self._hash.match(hashed_message)
        else:
            return self._hash == hashed_message

    def check_limit(self, value):
        raise NotImplementedError

    def check(self, message, value):
        if self.check_hash(message):
            return self.check_limit(limit)
        return False


class MaxLimit(Limit):

    def check_limit(self, value):
        return self._limit > value


class MinRemainingLimit(Limit):

    def check_limit(self, value):
        return self._limit  value

