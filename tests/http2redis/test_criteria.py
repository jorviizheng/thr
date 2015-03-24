from tornado.httputil import HTTPServerRequest
from tornado import testing

from thr.http2redis.rules import Criteria, regexp, glob


class TestCriteria(testing.AsyncTestCase):

    @testing.gen_test
    def test_method_match(self):
        request = HTTPServerRequest(method='GET', uri='/')
        criteria = Criteria(method='GET')
        result = yield criteria.match(request)
        self.assertTrue(result)

    @testing.gen_test
    def test_method_does_not_match(self):
        request = HTTPServerRequest(method='GET', uri='/')
        criteria = Criteria(method='POST')
        result = yield criteria.match(request)
        self.assertFalse(result)

    @testing.gen_test
    def test_path_match(self):
        request = HTTPServerRequest(uri='/foo/bar')
        criteria = Criteria(path=regexp('^/foo.*$'))
        result = yield criteria.match(request)
        self.assertTrue(result)

    @testing.gen_test
    def test_path_does_not_match(self):
        request = HTTPServerRequest(uri='/quux/bar')
        criteria = Criteria(path=regexp('^/foo.*$'))
        result = yield criteria.match(request)
        self.assertFalse(result)

    @testing.gen_test
    def test_match_function(self):
        def criterion_function(path):
            return True
        request = HTTPServerRequest(uri='/foo/bar')
        criteria = Criteria(request=criterion_function)
        result = yield criteria.match(request)
        self.assertTrue(result)

    @testing.gen_test
    def test_does_not_match_function(self):
        def criterion_function(path):
            return False
        request = HTTPServerRequest(uri='/foo/bar')
        criteria = Criteria(request=criterion_function)
        result = yield criteria.match(request)
        self.assertFalse(result)

    @testing.gen_test
    def test_remote_ip_match(self):
        request = HTTPServerRequest(uri='/')
        request.remote_ip = '10.0.0.1'
        criteria = Criteria(remote_ip=glob('10.0.0.*'))
        result = yield criteria.match(request)
        self.assertTrue(result)

    @testing.gen_test
    def test_remote_ip_does_not_match(self):
        request = HTTPServerRequest(uri='/')
        request.remote_ip = '10.0.0.1'
        criteria = Criteria(remote_ip=glob('10.0.1.*'))
        result = yield criteria.match(request)
        self.assertFalse(result)

    @testing.gen_test
    def test_remote_ip_does_not_match_function(self):
        def criterion_function(arg):
            return False
        request = HTTPServerRequest(uri='/')
        request.remote_ip = '10.0.0.1'
        criteria = Criteria(remote_ip=criterion_function)
        result = yield criteria.match(request)
        self.assertFalse(result)
