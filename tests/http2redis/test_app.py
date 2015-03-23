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
        data = json.loads(result[1].decode())
        self.assertEqual(data['path'], '/quux')

    @mock.patch('thr.http2redis.app.make_unique_id')
    @gen_test
    def test_read_something_from_response_key(self, make_unique_id_mock):
        reply_key = '---reply-key---'
        make_unique_id_mock.return_value = reply_key
        add_rule(Criteria(path='/quux'), Actions(set_queue='test-queue'))
        redis = tornadis.Client()
        yield redis.connect()
        yield redis.call('DEL', reply_key)
        yield redis.call('LPUSH', reply_key, 'reply-string')

        response = yield self.http_client.fetch(self.get_url('/quux'))

        self.assertIn('reply-string', response.body.decode(),
                      "We should get data from the reply queue")
        result = yield redis.call('RPOP', reply_key)
        self.assertIsNone(result, "Reply queue should now be empty")

    @gen_test
    def test_coroutine_rule(self):
        @tornado.gen.coroutine
        def coroutine_rule(request):
            return False
        add_rule(Criteria(path=coroutine_rule), Actions(set_queue='no-match'),
                 stop=1)
        add_rule(Criteria(path='/quux'), Actions(set_queue='test-queue'))
        yield self.http_client.fetch(self.get_url('/quux'))
        redis = tornadis.Client()
        yield redis.connect()
        result = yield redis.call('BRPOP', 'test-queue', 1)
        data = json.loads(result[1].decode())
        self.assertEqual(data['path'], '/quux')
