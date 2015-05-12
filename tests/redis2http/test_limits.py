# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from unittest import TestCase
from tornado.httputil import HTTPServerRequest
import mock

from six import assertCountEqual

from thr.redis2http.limits import Limits, MaxLimit, MinRemainingLimit
from thr.redis2http.limits import add_max_limit, add_min_remaining_limit
from thr.redis2http.counter import set_counter, del_counter
from thr.utils import glob, regexp


def uri_hash_func(message):
    return message.uri


def method_hash_func(message):
    return message.method


class TestLimits(TestCase):

    def setUp(self):
        super(TestLimits, self).setUp()
        Limits.reset()
        self.make_uuid_predictable()

    def make_uuid_predictable(self):
        patcher = mock.patch('uuid.uuid4')
        self.addCleanup(patcher.stop)
        mock_object = patcher.start()
        mock_object.return_value = "uuid"

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

        set_counter('uuid_/foo', 3)

        message = HTTPServerRequest("GET", "/foo")
        hashes = yield Limits.check(message)
        self.assertEqual(hashes, ["uuid_/foo"])

        set_counter('uuid_POST', 0)
        message = HTTPServerRequest("POST", "/foo")
        hashes = yield Limits.check(message)
        self.assertFalse(hashes)

        del_counter('uuid_/foo')
        del_counter('uuid_POST')

    def test_three_max_limits(self):
        add_max_limit(uri_hash_func, "/foo", 4)
        add_max_limit(uri_hash_func, "/bar", 3)
        add_max_limit(method_hash_func, "POST", 2)

        set_counter('uuid_/foo', 3)
        message = HTTPServerRequest("GET", "/foo")
        hashes = yield Limits.check(message)
        self.assertEqual(hashes, ["uuid_/foo"])

        set_counter('uuid_POST', 1)
        message = HTTPServerRequest("POST", "/foo")
        hashes = yield Limits.check(message)
        assertCountEqual(self, hashes, ["uuid_/foo", "uuid_POST"])

        set_counter('uuid_/bar', 4)
        message = HTTPServerRequest("GET", "/bar")
        hashes = yield Limits.check(message)
        self.assertFalse(hashes)

        del_counter('uuid_/foo')
        del_counter('uuid_POST')
        del_counter('uuid_/bar')

    def test_glob_limit(self):
        add_max_limit(uri_hash_func, glob("/foo*"), 2)

        set_counter('uuid_/foo*', 3)
        message = HTTPServerRequest("GET", "/foo")
        hashes = yield Limits.check(message)
        self.assertFalse(hashes)

        set_counter('uuid_/foo*', 0)
        message = HTTPServerRequest("GET", "/bar")
        hashes = yield Limits.check(message)
        self.assertEqual(hashes, [])

        message = HTTPServerRequest("GET", "/foobar")
        hashes = yield Limits.check(message)
        self.assertEqual(hashes, ["uuid_/foo*"])

        del_counter('uuid_/foo*')

    def test_regexp_limit(self):
        add_min_remaining_limit(method_hash_func, regexp("[A-Z]{4}"), 1)

        set_counter('uuid_[A-Z]{4}', 3)
        message = HTTPServerRequest("GET", "/foo")
        hashes = yield Limits.check(message)
        self.assertEqual(hashes, [])

        message = HTTPServerRequest("HEAD", "/foo")
        hashes = yield Limits.check(message)
        self.assertEqual(hashes, ["uuid_[A-Z]{4}"])

        set_counter('uuid_[A-Z]{4}', 0)
        message = HTTPServerRequest("POST", "/foo")
        hashes = yield Limits.check(message)
        self.assertFalse(hashes)

        del_counter('uuid_[A-Z]{4}')
