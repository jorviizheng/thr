from tornado.httputil import HTTPServerRequest
from tornado import gen
from unittest import TestCase

from thr.http2redis import HTTPExchange
from thr.http2redis.rules import Actions


class TestActions(TestCase):

    def test_set_input_header(self):
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_input_header=('Header-Name', 'header value'))
        actions.execute(exchange)
        self.assertEqual(request.headers['Header-Name'], 'header value')

    def test_set_status_code(self):
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_status_code=201)
        actions.execute(exchange)
        self.assertEqual(exchange.response['status_code'], 201)

    def test_set_status_code_with_callable(self):
        def callback(request):
            return 201
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_status_code=callback)
        actions.execute(exchange)
        self.assertEqual(exchange.response['status_code'], 201)

    def test_queue_with_callable(self):
        def callback(request):
            return 'test-queue'
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_queue=callback)
        actions.execute(exchange)
        self.assertEqual(exchange.queue, 'test-queue')

    def test_set_input_header_with_callable(self):
        def callback(request):
            return ('Header-Name', 'header value')
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_input_header=callback)
        actions.execute(exchange)
        self.assertEqual(request.headers['Header-Name'], 'header value')
