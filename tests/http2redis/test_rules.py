from tornado.httputil import HTTPServerRequest
from unittest import TestCase

from thr.http2redis import HTTPExchange
from thr.http2redis.rules import Criteria, Actions, Rules, add_rule


class TestRules(TestCase):

    def setUp(self):
        Rules.reset()

    def test_add_rule(self):
        add_rule(Criteria(), Actions())
        self.assertEqual(Rules.count(), 1)

    def test_execute_rules(self):
        add_rule(Criteria(path='/foo'),
                 Actions(set_input_header=('Header-Name', 'FOO')))
        add_rule(Criteria(path='/bar'),
                 Actions(set_input_header=('Header-Name', 'BAR')))
        request = HTTPServerRequest(method='GET', uri='/foo')
        Rules.execute_input_actions(HTTPExchange(request))
        self.assertEqual(request.headers['Header-Name'], 'FOO')

    def test_execute_multiple_rules(self):
        add_rule(Criteria(path='/foo'),
                 Actions(set_input_header=('Header-Name', 'FOO')))
        add_rule(Criteria(path='/foo'),
                 Actions(set_input_header=('Header-Name', 'BAR')))
        request = HTTPServerRequest(method='GET', uri='/foo')
        Rules.execute_input_actions(HTTPExchange(request))
        self.assertEqual(request.headers['Header-Name'], 'BAR')

    def test_stop_option(self):
        add_rule(Criteria(path='/foo'),
                 Actions(set_input_header=('Header-Name', 'FOO')), stop=True)
        add_rule(Criteria(path='/foo'),
                 Actions(set_input_header=('Header-Name', 'BAR')))
        request = HTTPServerRequest(method='GET', uri='/foo')
        Rules.execute_input_actions(HTTPExchange(request))
        self.assertEqual(request.headers['Header-Name'], 'FOO')

    def test_set_queue_based_on_path(self):
        add_rule(Criteria(path='/foo'), Actions(set_queue='test-queue'))
        request = HTTPServerRequest(method='GET', uri='/foo')
        exchange = HTTPExchange(request)
        Rules.execute_input_actions(exchange)
        self.assertEqual(exchange.queue, 'test-queue')

    def test_set_queue_based_on_callable(self):

        def callback_false(request):
            return False

        def callback_true(request):
            return True

        add_rule(Criteria(request=callback_false),
                 Actions(set_queue='not-this-one'), stop=1)
        add_rule(Criteria(request=callback_true),
                 Actions(set_queue='yes-this-one'))
        request = HTTPServerRequest(method='GET', uri='/foo')
        exchange = HTTPExchange(request)
        Rules.execute_input_actions(exchange)
        self.assertEqual(exchange.queue, 'yes-this-one')
