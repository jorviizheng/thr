# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from unittest import TestCase
from tornado.httputil import HTTPServerRequest
import mock

from six import assertCountEqual

from thr.redis2http.limits import Limits, Limit
from thr.redis2http.limits import add_max_limit
from thr.redis2http.counter import set_counter, del_counter
from thr.utils import glob, regexp, diff


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
        add_max_limit("foo", uri_hash_func, "/foo", 4)
        self.assertEqual(len(Limits.limits), 1)
        add_max_limit("post", method_hash_func, "POST", 1)
        self.assertEqual(len(Limits.limits), 2)
        self.assertIsInstance(Limits.limits["foo"],
                              Limit)
        self.assertIsInstance(Limits.limits["post"],
                              Limit)

    def test_simple_limits(self):
        add_max_limit("foo", uri_hash_func, "/foo", 4)
        add_max_limit("get", method_hash_func, diff("GET"), 1)

        set_counter('foo', 3)

        message = HTTPServerRequest("GET", "/foo")
        hashes = Limits.check(message)
        self.assertEqual(hashes, ["foo"])

        set_counter('get', 2)
        message = HTTPServerRequest("POST", "/foo")
        hashes = Limits.check(message)
        self.assertFalse(hashes)

        del_counter('foo')
        del_counter('get')

    def test_three_max_limits(self):
        add_max_limit("foo", uri_hash_func, "/foo", 4)
        add_max_limit("bar", uri_hash_func, "/bar", 3)
        add_max_limit("post", method_hash_func, "POST", 2)

        set_counter('foo', 3)
        message = HTTPServerRequest("GET", "/foo")
        hashes = Limits.check(message)
        self.assertEqual(hashes, ["foo"])

        set_counter('post', 1)
        message = HTTPServerRequest("POST", "/foo")
        hashes = Limits.check(message)
        assertCountEqual(self, hashes, ["foo", "post"])

        set_counter('bar', 4)
        message = HTTPServerRequest("GET", "/bar")
        hashes = Limits.check(message)
        self.assertFalse(hashes)

        del_counter('foo')
        del_counter('post')
        del_counter('bar')

    def test_glob_limit(self):
        add_max_limit("foo", uri_hash_func, glob("/foo*"), 2)

        set_counter('foo', 3)
        message = HTTPServerRequest("GET", "/foo")
        hashes = Limits.check(message)
        self.assertFalse(hashes)

        set_counter('foo', 0)
        message = HTTPServerRequest("GET", "/bar")
        hashes = Limits.check(message)
        self.assertEqual(hashes, [])

        message = HTTPServerRequest("GET", "/foobar")
        hashes = Limits.check(message)
        self.assertEqual(hashes, ["foo"])

        del_counter('uuid_/foo*')

    def test_regexp_limit(self):
        add_max_limit("regexp", method_hash_func, regexp("[A-Z]{4}"), 3)

        set_counter('regexp', 2)
        message = HTTPServerRequest("GET", "/foo")
        hashes = Limits.check(message)
        self.assertEqual(hashes, [])

        message = HTTPServerRequest("HEAD", "/foo")
        hashes = Limits.check(message)
        self.assertEqual(hashes, ["regexp"])

        set_counter('regexp', 5)
        message = HTTPServerRequest("POST", "/foo")
        hashes = Limits.check(message)
        self.assertFalse(hashes)

        del_counter('regexp')
