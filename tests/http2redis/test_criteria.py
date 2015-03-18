from tornado.httputil import HTTPServerRequest
from unittest import TestCase

from thr.http2redis.rules import Criteria, regexp, glob


class TestCriteria(TestCase):

    def test_method_match(self):
        request = HTTPServerRequest(method='GET', uri='/')
        criteria = Criteria(method='GET')
        self.assertTrue(criteria.match(request))

    def test_method_does_not_match(self):
        request = HTTPServerRequest(method='GET', uri='/')
        criteria = Criteria(method='POST')
        self.assertFalse(criteria.match(request))

    def test_path_match(self):
        request = HTTPServerRequest(uri='/foo/bar')
        criteria = Criteria(path=regexp('^/foo.*$'))
        self.assertTrue(criteria.match(request))

    def test_path_does_not_match(self):
        request = HTTPServerRequest(uri='/quux/bar')
        criteria = Criteria(path=regexp('^/foo.*$'))
        self.assertFalse(criteria.match(request))

    def test_path_match_function(self):
        def criterion_function(path):
            return True
        request = HTTPServerRequest(uri='/foo/bar')
        criteria = Criteria(path=criterion_function)
        self.assertTrue(criteria.match(request))

    def test_path_does_not_match_function(self):
        def criterion_function(path):
            return False
        request = HTTPServerRequest(uri='/foo/bar')
        criteria = Criteria(path=criterion_function)
        self.assertFalse(criteria.match(request))

    def test_remote_ip_match(self):
        request = HTTPServerRequest(uri='/')
        request.remote_ip = '10.0.0.1'
        criteria = Criteria(remote_ip=glob('10.0.0.*'))
        self.assertTrue(criteria.match(request))

    def test_remote_ip_does_not_match(self):
        request = HTTPServerRequest(uri='/')
        request.remote_ip = '10.0.0.1'
        criteria = Criteria(remote_ip=glob('10.0.1.*'))
        self.assertFalse(criteria.match(request))

    def test_remote_ip_match_function(self):
        def criterion_function(path):
            return True
        request = HTTPServerRequest(uri='/')
        request.remote_ip = '10.0.0.1'
        criteria = Criteria(remote_ip=criterion_function)
        self.assertTrue(criteria.match(request))

    def test_remote_ip_does_not_match_function(self):
        def criterion_function(arg):
            return False
        request = HTTPServerRequest(uri='/')
        request.remote_ip = '10.0.0.1'
        criteria = Criteria(remote_ip=criterion_function)
        self.assertFalse(criteria.match(request))
