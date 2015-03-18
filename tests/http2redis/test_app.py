from tornado.testing import AsyncHTTPTestCase, gen_test

from thr.http2redis.app import make_app
from thr.http2redis.rules import add_rule, Criteria, Actions


class TestApp(AsyncHTTPTestCase):

    def setUp(self):
        super(Http2Redis, self).setUp()
        add_rule(Criteria(path='/foo'), Actions(set_status_code=201))
        add_rule(Criteria(path='/bar'), Actions(set_status_code=202))

    def get_app(self):
        return make_app()

    @gen_test
    def test_201(self):
        response = yield self.http_client.fetch(self.get_url('/foo'))
        self.assertEqual(response.code, 201)

    @gen_test
    def test_202(self):
        response = yield self.http_client.fetch(self.get_url('/bar'))
        self.assertEqual(response.code, 202)
