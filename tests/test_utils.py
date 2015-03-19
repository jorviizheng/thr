# -*- coding: utf-8 -*-

from tornado.httputil import HTTPServerRequest
from unittest import TestCase

from thr.utils import make_unique_id, serialize_http_request


class TestUtils(TestCase):

    def test_make_unique_id(self):
        id1 = make_unique_id()
        id2 = make_unique_id()
        self.assertTrue(len(id1) > 10)
        self.assertTrue(len(id2) > 10)
        self.assertTrue(id1 != id2)

    def test_serialize1(self):
        uri = "/foo/bar/?foo=ééé&bar=simple&foo2=simple2&bar2"
        req = HTTPServerRequest(method='GET', uri=uri)
        serialize_http_request(req)
        # FIXME: check
