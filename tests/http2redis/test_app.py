import json
import mock
import tornado
from tornado.testing import AsyncHTTPTestCase, gen_test
import tornadis

from thr.http2redis.app import make_app
from thr.http2redis.rules import add_rule, Criteria, Actions, Rules


class TestApp(AsyncHTTPTestCase):

    def setUp(self):
        super(TestApp, self).setUp()
        self.redis = tornadis.Client()
        Rules.reset()
        add_rule(Criteria(path='/foo'), Actions(set_status_code=201))
        add_rule(Criteria(path='/bar'), Actions(set_status_code=202))
        self.make_response_key_predictable()

    def make_response_key_predictable(self):
        self.response_key = '---response-key---'
        patcher = mock.patch('thr.http2redis.app.make_unique_id')
        self.addCleanup(patcher.stop)
        mock_object = patcher.start()
        mock_object.return_value = self.response_key

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
        yield self.redis.connect()
        yield self.redis.call('DEL', 'test-queue')
        yield self.http_client.fetch(self.get_url('/quux'))
        result = yield self.redis.call('BRPOP', 'test-queue', 1)
        data = json.loads(result[1].decode())
        self.assertEqual(data['path'], '/quux')
        self.assertEqual(data['extra']['response_key'], self.response_key)

    @gen_test
    def test_read_something_from_response_key(self):
        add_rule(Criteria(path='/quux'), Actions(set_queue='test-queue'))
        yield self.redis.connect()
        yield self.redis.call('DEL', self.response_key)
        yield self.redis.call('LPUSH', self.response_key, 'response-string')

        response = yield self.http_client.fetch(self.get_url('/quux'))

        self.assertIn('response-string', response.body.decode(),
                      "We should get data from the response queue")
        result = yield self.redis.call('RPOP', self.response_key)
        self.assertIsNone(result, "Reply queue should now be empty")

    @gen_test
    def test_matching_coroutine_rule(self):

        @tornado.gen.coroutine
        def coroutine_rule(request):
            yield tornado.gen.maybe_future(None)
            raise tornado.gen.Return(False)

        add_rule(Criteria(path=coroutine_rule), Actions(set_queue='no-match'),
                 stop=1)
        add_rule(Criteria(path='/quux'), Actions(set_queue='test-queue'))
        yield self.http_client.fetch(self.get_url('/quux'))
        yield self.redis.connect()
        result = yield self.redis.call('BRPOP', 'test-queue', 1)
        data = json.loads(result[1].decode())
        self.assertEqual(data['path'], '/quux')

    @gen_test
    def test_non_matching_coroutine_rule(self):
        Rules.reset()

        @tornado.gen.coroutine
        def coroutine_rule(request):
            yield tornado.gen.maybe_future(None)
            raise tornado.gen.Return(True)

        add_rule(Criteria(request=coroutine_rule),
                 Actions(set_queue='test-queue'),
                 stop=1)
        add_rule(Criteria(path='/quux'), Actions(set_queue='no-match'))
        yield self.http_client.fetch(self.get_url('/quux'))
        yield self.redis.connect()
        result = yield self.redis.call('BRPOP', 'test-queue', 1)
        data = json.loads(result[1].decode())
        self.assertEqual(data['path'], '/quux')

    @gen_test
    def test_coroutine_action(self):
        # FIXME
        pass