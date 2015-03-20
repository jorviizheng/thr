# -*- coding: utf-8 -*-

from tornado.httputil import HTTPServerRequest
from unittest import TestCase

from thr.utils import make_unique_id, serialize_http_request
from thr.utils import unserialize_message


class TestUtils(TestCase):

    def test_make_unique_id(self):
        id1 = make_unique_id()
        id2 = make_unique_id()
        self.assertTrue(len(id1) > 10)
        self.assertTrue(len(id2) > 10)
        self.assertTrue(id1 != id2)

    def test_serialize_basic(self):
        uri = "/foo/bar"
        req = HTTPServerRequest(method='GET', uri=uri)
        req.remote_ip = "127.0.0.1"
        msg = serialize_http_request(req)
        (hreq, body_link, http_dict, extra_dict) = unserialize_message(msg)
        self.assertEquals(hreq.method, 'GET')
        self.assertTrue(body_link is None)
        self.assertEquals(len(extra_dict), 0)
        self.assertEquals(hreq.url, "http://127.0.0.1" + uri)
        self.assertEquals(http_dict['remote_ip'], "127.0.0.1")
        self.assertEquals(http_dict['host'], "127.0.0.1")
        self.assertEquals(hreq.body, None)
        self.assertEquals(body_link, None)

    def test_serialize_dict_to_inject(self):
        uri = "/foo/bar"
        req = HTTPServerRequest(method='GET', uri=uri)
        msg = serialize_http_request(req,
                                     dict_to_inject={"foo": "foo1",
                                                     "bar": "bar1"})
        (hreq, body_link, http_dict, extra_dict) = unserialize_message(msg)
        self.assertEquals(len(extra_dict), 2)
        self.assertEquals(extra_dict['foo'], "foo1")
        self.assertEquals(extra_dict['bar'], "bar1")

    def test_serialize_body(self):
        uri = "/foo/bar"
        req = HTTPServerRequest(method='PUT', uri=uri, body="foo")
        msg = serialize_http_request(req)
        (hreq, body_link, http_dict, extra_dict) = unserialize_message(msg)
        self.assertEquals(hreq.method, 'PUT')
        self.assertEquals(hreq.body.decode(), "foo")
        self.assertEquals(body_link, None)
