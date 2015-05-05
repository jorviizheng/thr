# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import tornado
import tornadis
from tornado.testing import AsyncTestCase, gen_test
from tornado.httputil import HTTPServerRequest
import mock

from six import assertCountEqual

from thr.redis2http.limits import Limits, MaxLimit, MinRemainingLimit
from thr.redis2http.limits import add_max_limit, add_min_remaining_limit
from thr.utils import glob, regexp


def uri_hash_func(message):
    return message.uri


def method_hash_func(message):
    return message.method


class TestLimits(AsyncTestCase):

    def setUp(self):
        super(TestLimits, self).setUp()
        Limits.reset()
        self.make_uuid_predictable()

    def get_new_ioloop(self):
        return tornado.ioloop.IOLoop.instance()

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

    @gen_test
    def test_simple_limits(self):
        add_max_limit(uri_hash_func, "/foo", 4)
        add_min_remaining_limit(method_hash_func, "POST", 1)

        client = tornadis.Client()
        yield client.connect()
        yield client.call('SET', 'uuid_/foo', 3)

        message = HTTPServerRequest("GET", "/foo")
        hashes = yield Limits.check(message)
        self.assertEqual(hashes, ["uuid_/foo"])

        yield client.call('SET', 'uuid_POST', 0)
        message = HTTPServerRequest("POST", "/foo")
        hashes = yield Limits.check(message)
        self.assertFalse(hashes)

        yield client.call('DEL', 'uuid_/foo')
        yield client.call('DEL', 'uuid_POST')
        yield client.disconnect()

    @gen_test
    def test_three_max_limits(self):
        add_max_limit(uri_hash_func, "/foo", 4)
        add_max_limit(uri_hash_func, "/bar", 3)
        add_max_limit(method_hash_func, "POST", 2)

        client = tornadis.Client()
        yield client.connect()

        yield client.call('SET', 'uuid_/foo', 3)
        message = HTTPServerRequest("GET", "/foo")
        hashes = yield Limits.check(message)
        self.assertEqual(hashes, ["uuid_/foo"])

        yield client.call('SET', 'uuid_POST', 1)
        message = HTTPServerRequest("POST", "/foo")
        hashes = yield Limits.check(message)
        assertCountEqual(self, hashes, ["uuid_/foo", "uuid_POST"])

        yield client.call('SET', 'uuid_/bar', 4)
        message = HTTPServerRequest("GET", "/bar")
        hashes = yield Limits.check(message)
        self.assertFalse(hashes)

        yield client.call('DEL', 'uuid_/foo')
        yield client.call('DEL', 'uuid_POST')
        yield client.call('DEL', 'uuid_/bar')
        yield client.disconnect()

    @gen_test
    def test_glob_limit(self):
        add_max_limit(uri_hash_func, glob("/foo*"), 2)

        client = tornadis.Client()
        yield client.connect()

        yield client.call('SET', 'uuid_/foo*', 3)
        message = HTTPServerRequest("GET", "/foo")
        hashes = yield Limits.check(message)
        self.assertFalse(hashes)

        yield client.call('SET', 'uuid_/foo*', 0)
        message = HTTPServerRequest("GET", "/bar")
        hashes = yield Limits.check(message)
        self.assertEqual(hashes, [])

        message = HTTPServerRequest("GET", "/foobar")
        hashes = yield Limits.check(message)
        self.assertEqual(hashes, ["uuid_/foo*"])

        yield client.call('DEL', 'uuid_/foo*')
        yield client.disconnect()

    @gen_test
    def test_regexp_limit(self):
        add_min_remaining_limit(method_hash_func, regexp("[A-Z]{4}"), 1)

        client = tornadis.Client()
        yield client.connect()

        yield client.call('SET', 'uuid_[A-Z]{4}', 3)
        message = HTTPServerRequest("GET", "/foo")
        hashes = yield Limits.check(message)
        self.assertEqual(hashes, [])

        message = HTTPServerRequest("HEAD", "/foo")
        hashes = yield Limits.check(message)
        self.assertEqual(hashes, ["uuid_[A-Z]{4}"])

        yield client.call('SET', 'uuid_[A-Z]{4}', 0)
        message = HTTPServerRequest("POST", "/foo")
        hashes = yield Limits.check(message)
        self.assertFalse(hashes)

        yield client.call('DEL', 'uuid_[A-Z]{4}')
        yield client.disconnect()
