from tornado.httputil import HTTPServerRequest
from unittest import TestCase

from thr.http2redis import Exchange
from thr.http2redis.rules import Criteria, Actions, Rules, add_rule


class TestRules(TestCase):

    def test_add_rule(self):
        Rules.reset()
        add_rule(Criteria(), Actions())
        self.assertEqual(Rules.count(), 1)

    def test_execute_rules(self):
        add_rule(Criteria(path='/foo'), Actions(set_input_header=('Header-Name', 'FOO')))
        add_rule(Criteria(path='/bar'), Actions(set_input_header=('Header-Name', 'BAR')))
        request = HTTPServerRequest(method='GET', uri='/foo')
        Rules.execute(Exchange(request))
        self.assertEqual(request.headers['Header-Name'], 'FOO')

    def test_execute_multiple_rules(self):
        add_rule(Criteria(path='/foo'), Actions(set_input_header=('Header-Name', 'FOO')))
        add_rule(Criteria(path='/foo'), Actions(set_input_header=('Header-Name', 'BAR')))
        request = HTTPServerRequest(method='GET', uri='/foo')
        Rules.execute(Exchange(request))
        self.assertEqual(request.headers['Header-Name'], 'BAR')

    def test_stop_option(self):
        add_rule(Criteria(path='/foo'), Actions(set_input_header=('Header-Name', 'FOO')), stop=True)
        add_rule(Criteria(path='/foo'), Actions(set_input_header=('Header-Name', 'BAR')))
        request = HTTPServerRequest(method='GET', uri='/foo')
        Rules.execute(Exchange(request))
        self.assertEqual(request.headers['Header-Name'], 'FOO')
