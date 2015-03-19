import tornado
from tornado.testing import AsyncHTTPTestCase, gen_test
import tornadis

from thr.http2redis.app import make_app
from thr.http2redis.rules import add_rule, Criteria, Actions, Rules


class TestApp(AsyncHTTPTestCase):

    def setUp(self):
        super(TestApp, self).setUp()
        Rules.reset()
        add_rule(Criteria(path='/foo'), Actions(set_status_code=201))
        add_rule(Criteria(path='/bar'), Actions(set_status_code=202))

    def get_new_ioloop(self):
        return tornado.ioloop.IOLoop.instance()

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

    @gen_test
    def test_write_something_to_queue(self):
        add_rule(Criteria(path='/quux'), Actions(set_queue='test-queue'))
        yield self.http_client.fetch(self.get_url('/quux'))
        redis = tornadis.Client()
        yield redis.connect()
        result = yield redis.call('BRPOP', 'test-queue', 1)
        self.assertEqual(result[1], '/quux')
