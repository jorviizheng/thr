from tornado.httputil import HTTPServerRequest
from unittest import TestCase

from thr.http2redis import Exchange
from thr.http2redis.rules import Actions


class TestCriteria(TestCase):

    def test_set_input_header(self):
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = Exchange(request)
        actions = Actions(set_input_header=('Header-Name', 'header value'))
        actions.execute(exchange)
        self.assertEqual(request.headers['Header-Name'], 'header value')

    def test_set_status_code(self):
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = Exchange(request)
        actions = Actions(set_status_code=201)
        actions.execute(exchange)
        self.assertEqual(exchange.response['status_code'], 201)
