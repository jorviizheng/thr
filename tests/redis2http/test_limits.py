# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from unittest import TestCase
from mock import patch
from tornado.httputil import HTTPServerRequest

from thr.redis2http.limits import Limits, MaxLimit, MinRemainingLimit
from thr.redis2http.limits import add_max_limit, add_min_remaining_limit
from thr.utils import glob, regexp


def uri_hash_func(message):
    return message.uri


def method_hash_func(message):
    return message.method


class TestLimits(TestCase):

    def setUp(self):
        Limits.reset()
        self.get_workers_mock = patch("thr.redis2http.limits.get_busy_workers",
                                      side_effect=[3, 0, 0, 4])
        self.get_workers_mock.start()

    def tearDown(self):
        self.get_workers_mock.stop()

    def test_add_limit(self):
        add_max_limit(uri_hash_func, "/foo", 4)
        self.assertEqual(len(Limits.limits), 1)
        add_min_remaining_limit(method_hash_func, "POST", 1)
        self.assertEqual(len(Limits.limits), 2)
        self.assertIsInstance(Limits.limits[uri_hash_func][0],
                              MaxLimit)
        self.assertIsInstance(Limits.limits[method_hash_func][0],
                              MinRemainingLimit)

    def test_simple_limits(self):
        add_max_limit(uri_hash_func, "/foo", 4)
        add_min_remaining_limit(method_hash_func, "POST", 1)

        message = HTTPServerRequest("GET", "/foo")
        hashes = Limits.check(message)
        self.assertEqual(hashes, ["/foo"])

        message = HTTPServerRequest("POST", "/foo")
        hashes = Limits.check(message)
        self.assertFalse(hashes)

    def test_three_max_limits(self):
        add_max_limit(uri_hash_func, "/foo", 4)
        add_max_limit(uri_hash_func, "/bar", 3)
        add_max_limit(method_hash_func, "POST", 2)

        message = HTTPServerRequest("GET", "/foo")
        hashes = Limits.check(message)
        self.assertEqual(hashes, ["/foo"])

        message = HTTPServerRequest("POST", "/foo")
        hashes = Limits.check(message)
        self.assertItemsEqual(hashes, ["/foo", "POST"])

        message = HTTPServerRequest("GET", "/bar")
        hashes = Limits.check(message)
        self.assertFalse(hashes)

    def test_glob_limit(self):
        add_max_limit(uri_hash_func, glob("/foo*"), 2)

        message = HTTPServerRequest("GET", "/foo")
        hashes = Limits.check(message)
        self.assertFalse(hashes)

        message = HTTPServerRequest("GET", "/bar")
        hashes = Limits.check(message)
        self.assertEqual(hashes, [])

        message = HTTPServerRequest("GET", "/foobar")
        hashes = Limits.check(message)
        self.assertEqual(hashes, ["/foo*"])

    def test_regexp_limit(self):
        add_min_remaining_limit(method_hash_func, regexp("[A-Z]{4}"), 1)

        message = HTTPServerRequest("GET", "/foo")
        hashes = Limits.check(message)
        self.assertEqual(hashes, [])

        message = HTTPServerRequest("HEAD", "/foo")
        hashes = Limits.check(message)
        self.assertEqual(hashes, ["[A-Z]{4}"])

        message = HTTPServerRequest("POST", "/foo")
        hashes = Limits.check(message)
        self.assertFalse(hashes)
