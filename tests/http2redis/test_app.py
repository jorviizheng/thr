# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import os
import json
import mock
import tornado
from tornado import gen
from tornado.testing import AsyncHTTPTestCase, gen_test
import tornadis

from thr.http2redis import app
from thr.http2redis.rules import add_rule, Criteria, Actions, Rules


class TestLoadConfigFile(AsyncHTTPTestCase):

    def get_new_ioloop(self):
        return tornado.ioloop.IOLoop.instance()

    def get_app(self):
        config_file = os.path.join(os.path.dirname(__file__), 'config.py')
        app.options.config = config_file
        return app.make_app()

    @gen_test
    def test_load_config_file(self):
        response = yield self.http_client.fetch(self.get_url('/foo'))
        self.assertEqual(response.code, 201)


class TestApp(AsyncHTTPTestCase):

    def setUp(self):
        super(TestApp, self).setUp()
        self.redis = tornadis.Client()
        Rules.reset()
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
        app.options.config = None
        app.options.timeout = 1
        return app.make_app()

    def add_basic_rules(self):
        add_rule(Criteria(path="/baz"), Actions(set_redis_queue="null"))
        add_rule(Criteria(path='/foo'), Actions(set_status_code=201))
        add_rule(Criteria(path='/bar'), Actions(set_status_code=202))

    @gen_test
    def test_get_201(self):
        self.add_basic_rules()
        response = yield self.http_client.fetch(self.get_url('/foo'))
        self.assertEqual(response.code, 201)

    @gen_test
    def test_post_202(self):
        self.add_basic_rules()
        response = yield self.http_client.fetch(self.get_url('/bar'),
                                                method="POST",
                                                body="whatever")
        self.assertEqual(response.code, 202)

    @gen_test
    def test_404(self):
        self.add_basic_rules()
        response = yield self.http_client.fetch(self.get_url('/baz'),
                                                raise_error=False)
        self.assertEqual(response.code, 404)

    @gen_test
    def test_write_something_to_queue(self):
        add_rule(Criteria(path='/quux'), Actions(set_redis_queue='test-queue'))
        yield self.redis.connect()
        yield self.redis.call('DEL', 'test-queue')
        yield self.http_client.fetch(self.get_url('/quux'), raise_error=False)
        result = yield self.redis.call('BRPOP', 'test-queue', 1)
        data = json.loads(result[1].decode())
        self.assertEqual(data['path'], '/quux')
        self.assertEqual(data['extra']['response_key'],
                         "thr:queue:response:%s" % self.response_key)

    @gen_test
    def test_matching_coroutine_rule(self):

        @tornado.gen.coroutine
        def coroutine_rule(request):
            yield tornado.gen.maybe_future(None)
            raise tornado.gen.Return(False)

        add_rule(Criteria(path=coroutine_rule),
                 Actions(set_redis_queue='no-match'),
                 stop=1)
        add_rule(Criteria(path='/quux'), Actions(set_redis_queue='test-queue'))
        yield self.http_client.fetch(self.get_url('/quux'), raise_error=False)
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
                 Actions(set_redis_queue='test-queue'),
                 stop=1)
        add_rule(Criteria(path='/quux'), Actions(set_redis_queue='no-match'))
        yield self.http_client.fetch(self.get_url('/quux'), raise_error=False)
        yield self.redis.connect()
        result = yield self.redis.call('BRPOP', 'test-queue', 1)
        data = json.loads(result[1].decode())
        self.assertEqual(data['path'], '/quux')

    @gen_test
    def test_coroutine_action(self):
        Rules.reset()

        @gen.coroutine
        def coroutine_action(request):
            yield gen.maybe_future(None)
            raise gen.Return(202)

        add_rule(Criteria(path='/quux'),
                 Actions(set_status_code=coroutine_action,
                         set_redis_queue='test-queue'),
                 stop=1)
        response = yield self.http_client.fetch(self.get_url('/quux'))
        self.assertEqual(response.code, 202)
