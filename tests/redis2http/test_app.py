# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import tornado
from tornado.testing import AsyncTestCase, gen_test
import tornadis
from datetime import datetime
from mock import patch

from six import BytesIO

from thr.redis2http.app import process_request
from thr.redis2http.limits import Limits
from thr.redis2http.exchange import HTTPRequestExchange
from thr.redis2http.queue import Queue
from thr.utils import serialize_http_request
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
    def test_process_request(self):
        @tornado.gen.coroutine
        def test_fetch(request, **kwargs):
            resp = tornado.httpclient.HTTPResponse(request, 200,
                                                   buffer=BytesIO(b"bar"))
            raise tornado.gen.Return(resp)

        fetch_patcher = patch("tornado.httpclient.AsyncHTTPClient.fetch")
        fetch_mock = fetch_patcher.start()
        fetch_mock.side_effect = test_fetch

        dct = {"response_key": "foobar"}
        req = tornado.httputil.HTTPServerRequest("GET", "/foo")
        msg = serialize_http_request(req, dict_to_inject=dct)
        exchange = HTTPRequestExchange(msg,
                                       Queue(["foo"], host="localhost",
                                             port=6379))
        yield process_request(exchange, datetime.now())
        fetch_patcher.stop()
        client = tornadis.Client()
        yield client.connect()
        res = yield client.call('BRPOP', 'foobar', 0)
        self.assertEquals(len(res), 2)
        (status_code, body, body_link, headers, extra_dict) = \
            unserialize_response_message(res[1])
        self.assertEquals(status_code, 200)
        self.assertEquals(body, b"bar")
        client.disconnect()
