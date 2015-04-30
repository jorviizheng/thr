# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import tornado
from tornado.testing import AsyncTestCase, gen_test
import tornadis
import unittest
from mock import patch

from six.moves import cStringIO

from thr.redis2http.app import request_redis_handler, request_queue
from thr.redis2http.app import request_toro_handler
from thr.redis2http.app import process_request, finalize_request
from thr.utils import serialize_http_request, serialize_http_response


def print_exception(future=None):
    import traceback
    exc = future.exc_info()
    if exc is not None:
        print exc[0]
        print exc[1]
        print traceback.format_tb(exc[2])
        raise exc


class TestRedis2HttpApp(AsyncTestCase):

    def setUp(self):
        super(TestRedis2HttpApp, self).setUp()

    def get_new_ioloop(self):
        return tornado.ioloop.IOLoop.instance()

    @gen_test
    def test_request_handler(self):
        self.io_loop.add_future(request_redis_handler('test_queue'),
                                print_exception)

        self.assertEqual(request_queue.qsize(), 0)

        client = tornadis.Client()
        request = tornado.httputil.HTTPServerRequest("GET", "/foo")
        serialized_message = serialize_http_request(request)
        yield client.connect()
        yield client.call('DEL', 'test_queue')
        yield client.call('LPUSH', 'test_queue', serialized_message)

        res = yield request_queue.get()
        self.assertItemsEqual(res, ['test_queue', serialized_message])

        yield client.call('DEL', 'test_queue')
        yield client.disconnect()

    @gen_test
    def test_process_request(self):
        @tornado.gen.coroutine
        def test_fetch(request, **kwargs):
            raise tornado.gen.Return('This should be an HttpResponse')

        fetch_patcher = patch("tornado.httpclient.AsyncHTTPClient.fetch")
        fetch_mock = fetch_patcher.start()
        fetch_mock.side_effect = test_fetch

        client = tornadis.Client()
        yield client.connect()
        yield client.call('DEL', 'hash_1')
        yield client.call('DEL', 'hash_2')
        yield client.call('SET', 'hash_1', 0)
        yield client.call('SET', 'hash_2', 3)

        request = tornado.httpclient.HTTPRequest("http://localhost/foo",
                                                 method="GET")
        response = yield process_request(request, ['hash_1', 'hash_2'])

        hash_1 = yield client.call('GET', 'hash_1')
        hash_2 = yield client.call('GET', 'hash_2')
        yield client.call('DEL', 'hash_1')
        yield client.call('DEL', 'hash_2')
        yield client.disconnect()

        self.assertEqual(response, 'This should be an HttpResponse')
        self.assertEqual(hash_1, '1')
        self.assertEqual(hash_2, '4')
        fetch_patcher.stop()

    @gen_test
    def test_finalize_request(self):
        request = tornado.httpclient.HTTPRequest("http://localhost/foo",
                                                 method="GET")
        response = tornado.httpclient.HTTPResponse(request, 200,
                                                   buffer=cStringIO("bar"))

        client = tornadis.Client()
        yield client.connect()
        yield client.call('DEL', 'test_key')
        yield client.call('DEL', 'hash_1')
        yield client.call('DEL', 'hash_2')
        yield client.call('SET', 'hash_1', 1)
        yield client.call('SET', 'hash_2', 4)

        self.io_loop.add_callback(finalize_request, 'test_key',
                                  ['hash_1', 'hash_2'], response)

        _, serialized_response = yield client.call('BRPOP', 'test_key', 0)
        hash_1 = yield client.call('GET', 'hash_1')
        hash_2 = yield client.call('GET', 'hash_2')

        self.assertEqual(serialize_http_response(response),
                         serialized_response)
        self.assertEqual(hash_1, '0')
        self.assertEqual(hash_2, '3')

        yield client.call('DEL', 'test_key')
        yield client.call('DEL', 'hash_1')
        yield client.call('DEL', 'hash_2')
        yield client.disconnect()

    @unittest.skip("Not working yet")
    @gen_test
    def test_toro_handler(self):
        @tornado.gen.coroutine
        def test_fetch(request, **kwargs):
            raise tornado.gen.Return('This should be an HttpResponse')

        fetch_patcher = patch("tornado.httpclient.AsyncHTTPClient.fetch")
        fetch_mock = fetch_patcher.start()
        fetch_mock.side_effect = test_fetch

        request = tornado.httputil.HTTPServerRequest("GET", "/foo")
        serialized_message = \
            serialize_http_request(request,
                                   dict_to_inject={"response_key": "test_key"})
        yield request_queue.put(['test_queue', serialized_message])
        self.io_loop.add_future(request_toro_handler(), print_exception)

        client = tornadis.Client()
        yield client.connect()
        _, serialized_response = yield client.call('BRPOP', 'test_key', 0)
        yield client.disconnect()

        self.assertEqual('toto', serialized_response)
