# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import tornado
from tornado.testing import AsyncTestCase, gen_test
import tornadis
from mock import patch
import json

from six import BytesIO

from thr.redis2http.app import request_redis_handler, get_request_queue
from thr.redis2http.app import request_toro_handler
from thr.redis2http.app import process_request
from thr.redis2http.limits import Limits, add_max_limit
from thr.redis2http.exchange import HTTPRequestExchange
from thr.redis2http.queue import Queue
from thr.redis2http.counter import get_counter, set_counter, del_counter
from thr.utils import glob, serialize_http_request
from thr.utils import unserialize_response_message


def raise_exception(future=None):
    exc = future.exc_info()
    if exc is not None:
        import traceback
        traceback.print_exception(*exc)
        raise exc


class TestRedis2HttpApp(AsyncTestCase):

    def setUp(self):
        super(TestRedis2HttpApp, self).setUp()
        Limits.reset()
        self.make_uuid_predictable()

    def get_new_ioloop(self):
        return tornado.ioloop.IOLoop.instance()

    def make_uuid_predictable(self):
        patcher = patch('uuid.uuid4')
        self.addCleanup(patcher.stop)
        mock_object = patcher.start()
        mock_object.return_value = "uuid"

    @gen_test
    def test_request_handler(self):
        self.io_loop.add_future(request_redis_handler(Queue('127.0.0.1', 6379,
                                                            'test_queue'),
                                                      True), raise_exception)

        self.assertEqual(get_request_queue().qsize(), 0)

        client = tornadis.Client()
        request = tornado.httputil.HTTPServerRequest("GET", "/foo")
        serialized_message = serialize_http_request(request)
        yield client.connect()
        yield client.call('DEL', 'test_queue')
        yield client.call('LPUSH', 'test_queue', serialized_message)

        priority, res = yield get_request_queue().get()
        self.assertEqual(res.queue.queue, u'test_queue')
        self.assertEqual(res.serialized_request, serialized_message)

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

        request = tornado.httpclient.HTTPRequest("http://localhost/foo",
                                                 method="GET")

        exchange = HTTPRequestExchange(request, Queue("localhost", 6379,
                                                      "foo"))
        response = yield process_request(exchange, [])

        self.assertEqual(response, u'This should be an HttpResponse')
        fetch_patcher.stop()

    @gen_test
    def test_finalize_request(self):
        request = tornado.httpclient.HTTPRequest("http://localhost/foo",
                                                 method="GET")
        response = tornado.httpclient.HTTPResponse(request, 200,
                                                   buffer=BytesIO(b"bar"))
        response_future = tornado.concurrent.Future()
        response_future.set_result(response)

        client = tornadis.Client()
        yield client.connect()
        yield client.call('DEL', 'test_key')
        set_counter('hash_1', 1)
        set_counter('hash_2', 4)

        self.io_loop.add_callback(finalize_request,
                                  Queue('127.0.0.1', 6379, 'whatever'),
                                  'test_key', ['hash_1', 'hash_2'],
                                  response_future)

        _, serialized_response = yield client.call('BRPOP', 'test_key', 0)
        hash_1 = get_counter('hash_1')
        hash_2 = get_counter('hash_2')

        self.assertEqual(serialize_http_response(response),
                         serialized_response)
        self.assertEqual(hash_1, 0)
        self.assertEqual(hash_2, 3)

        del_counter('hash_1')
        del_counter('hash_2')
        yield client.call('DEL', 'test_key')
        yield client.disconnect()

    @gen_test
    def test_toro_handler(self):
        @tornado.gen.coroutine
        def test_fetch(request, **kwargs):
            raise tornado.gen.Return(
                tornado.httpclient.HTTPResponse(request, 200,
                                                buffer=BytesIO(b"bar")))

        fetch_patcher = patch("tornado.httpclient.AsyncHTTPClient.fetch")
        fetch_mock = fetch_patcher.start()
        fetch_mock.side_effect = test_fetch

        Limits.reset()

        request = tornado.httputil.HTTPServerRequest("GET", "/foo")
        serialized_message = \
            serialize_http_request(request,
                                   dict_to_inject={"response_key": "test_key"})
        exchange = HTTPRequestExchange(serialized_message,
                                       Queue('127.0.0.1', 6379, 'test_queue'))

        yield get_request_queue().put((5, exchange))
        self.io_loop.add_future(request_toro_handler(True), raise_exception)

        client = tornadis.Client()
        yield client.connect()
        _, serialized_response = yield client.call('BRPOP', 'test_key', 0)
        yield client.disconnect()

        (status_code, body, _, headers, _) = \
            unserialize_response_message(serialized_response)
        self.assertEqual(status_code, 200)
        self.assertEqual(body, b"bar")
        self.assertEqual(len(headers), 0)
        fetch_mock = fetch_patcher.stop()

    @gen_test
    def test_toro_handler_with_limits(self):
        @tornado.gen.coroutine
        def test_fetch(request, **kwargs):
            raise tornado.gen.Return(
                tornado.httpclient.HTTPResponse(request, 200,
                                                buffer=BytesIO(b"bar")))

        fetch_patcher = patch("tornado.httpclient.AsyncHTTPClient.fetch")
        fetch_mock = fetch_patcher.start()
        fetch_mock.side_effect = test_fetch

        Limits.reset()
        add_max_limit(lambda r: r.url, glob("*/foo"), 3)

        set_counter('uuid_*/foo', 1)

        request = tornado.httputil.HTTPServerRequest("GET", "/foo")
        serialized_message = \
            serialize_http_request(request,
                                   dict_to_inject={"response_key": "test_key"})
        exchange = HTTPRequestExchange(serialized_message,
                                       Queue('127.0.0.1', 6379, 'test_queue'))
        yield get_request_queue().put((5, exchange))
        self.io_loop.add_future(request_toro_handler(True), raise_exception)

        client = tornadis.Client()
        yield client.connect()
        _, serialized_response = yield client.call('BRPOP', 'test_key', 0)
        yield client.disconnect()

        foo_counter = get_counter('uuid_*/foo')
        del_counter('uuid_*/foo')

        self.assertEqual(foo_counter, 1)
        (status_code, body, _, headers, _) = \
            unserialize_response_message(serialized_response)
        self.assertEqual(status_code, 200)
        self.assertEqual(body, b"bar")
        self.assertEqual(len(headers), 0)
        fetch_mock = fetch_patcher.stop()

    @gen_test
    def test_toro_handler_reinject(self):
        Limits.reset()
        add_max_limit(lambda r: r.url, glob("*/foo"), 3)

        set_counter('uuid_*/foo', 3)

        request = tornado.httputil.HTTPServerRequest("GET", "/foo")
        serialized_message = \
            serialize_http_request(request,
                                   dict_to_inject={"response_key": "test_key"})
        exchange = HTTPRequestExchange(serialized_message,
                                       Queue('127.0.0.1', 6379, 'test_queue'))
        yield get_request_queue().put((5, exchange))
        self.io_loop.add_future(request_toro_handler(True), raise_exception)

        client = tornadis.Client()
        yield client.connect()
        _, serialized_request = yield client.call('BRPOP', 'test_queue', 0)
        yield client.disconnect()
        del_counter('uuid_*/foo')

        self.assertEqual(
            {u'extra': {u'response_key': u'test_key'}, u'host': u'127.0.0.1',
             u'method': u'GET', u'path': u'/foo'},
            json.loads(serialized_request.decode()))
