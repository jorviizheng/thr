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

from thr.redis2http.app import request_redis_handler, request_queue
from thr.redis2http.app import request_toro_handler
from thr.redis2http.app import process_request, finalize_request
from thr.redis2http.limits import Limits, add_max_limit
from thr.utils import serialize_http_request, serialize_http_response, glob
from thr.utils import unserialize_response_message


def raise_exception(future=None):
    exc = future.exc_info()
    if exc is not None:
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
        self.io_loop.add_future(request_redis_handler('test_queue'),
                                raise_exception)

        self.assertEqual(request_queue.qsize(), 0)

        client = tornadis.Client()
        request = tornado.httputil.HTTPServerRequest("GET", "/foo")
        serialized_message = serialize_http_request(request)
        yield client.connect()
        yield client.call('DEL', 'test_queue')
        yield client.call('LPUSH', 'test_queue', serialized_message)

        res = yield request_queue.get()
        self.assertEqual(res[0].decode(), u'test_queue')
        self.assertEqual(res[1].decode(), serialized_message)

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

        self.assertEqual(response, u'This should be an HttpResponse')
        self.assertEqual(hash_1.decode(), u'1')
        self.assertEqual(hash_2.decode(), u'4')
        fetch_patcher.stop()

    @gen_test
    def test_process_request_with_body_link(self):
        @tornado.gen.coroutine
        def test_fetch(request, **kwargs):
            if request == "this is a body_link":
                raise tornado.gen.Return('There is your body')
            # We return the request to check it has been
            # correctly updated with the body
            raise tornado.gen.Return(request)

        fetch_patcher = patch("tornado.httpclient.AsyncHTTPClient.fetch")
        fetch_mock = fetch_patcher.start()
        fetch_mock.side_effect = test_fetch

        request = tornado.httpclient.HTTPRequest("http://localhost/foo",
                                                 method="GET")
        response = yield process_request(request, [], "this is a body_link")

        self.assertEqual(response.url, u'http://localhost/foo')
        self.assertEqual(response.body.decode(), u'There is your body')
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
        yield client.call('DEL', 'hash_1')
        yield client.call('DEL', 'hash_2')
        yield client.call('SET', 'hash_1', 1)
        yield client.call('SET', 'hash_2', 4)

        self.io_loop.add_callback(finalize_request, 'test_key',
                                  ['hash_1', 'hash_2'], response_future)

        _, serialized_response = yield client.call('BRPOP', 'test_key', 0)
        hash_1 = yield client.call('GET', 'hash_1')
        hash_2 = yield client.call('GET', 'hash_2')

        self.assertEqual(serialize_http_response(response),
                         serialized_response.decode())
        self.assertEqual(hash_1.decode(), u'0')
        self.assertEqual(hash_2.decode(), u'3')

        yield client.call('DEL', 'test_key')
        yield client.call('DEL', 'hash_1')
        yield client.call('DEL', 'hash_2')
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
        yield request_queue.put(['test_queue', serialized_message])
        self.io_loop.add_future(request_toro_handler(), raise_exception)

        client = tornadis.Client()
        yield client.connect()
        _, serialized_response = yield client.call('BRPOP', 'test_key', 0)
        yield client.disconnect()

        (status_code, body, _, headers, _) = \
            unserialize_response_message(serialized_response.decode())
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

        client = tornadis.Client()
        yield client.connect()
        yield client.call('DEL', 'uuid_*/foo')
        yield client.call('SET', 'uuid_*/foo', 1)

        request = tornado.httputil.HTTPServerRequest("GET", "/foo")
        serialized_message = \
            serialize_http_request(request,
                                   dict_to_inject={"response_key": "test_key"})
        yield request_queue.put(['test_queue', serialized_message])
        self.io_loop.add_future(request_toro_handler(), raise_exception)

        _, serialized_response = yield client.call('BRPOP', 'test_key', 0)
        foo_counter = yield client.call('GET', 'uuid_*/foo')
        yield client.call('DEL', 'uuid_*/foo')
        yield client.disconnect()

        self.assertEqual(foo_counter.decode(), u'1')
        (status_code, body, _, headers, _) = \
            unserialize_response_message(serialized_response.decode())
        self.assertEqual(status_code, 200)
        self.assertEqual(body, b"bar")
        self.assertEqual(len(headers), 0)
        fetch_mock = fetch_patcher.stop()

    @gen_test
    def test_toro_handler_reinject(self):
        Limits.reset()
        add_max_limit(lambda r: r.url, glob("*/foo"), 3)

        client = tornadis.Client()
        yield client.connect()
        yield client.call('DEL', 'uuid_*/foo')
        yield client.call('SET', 'uuid_*/foo', 3)

        request = tornado.httputil.HTTPServerRequest("GET", "/foo")
        serialized_message = \
            serialize_http_request(request,
                                   dict_to_inject={"response_key": "test_key"})
        yield request_queue.put(['test_queue', serialized_message])
        self.io_loop.add_future(request_toro_handler(), raise_exception)

        _, serialized_request = yield client.call('BRPOP', 'test_queue', 0)
        yield client.call('DEL', 'uuid_*/foo')
        yield client.disconnect()

        self.assertEqual(
            {u'extra': {u'response_key': u'test_key'}, u'host': u'127.0.0.1',
             u'method': u'GET', u'path': u'/foo'},
            json.loads(serialized_request.decode()))
