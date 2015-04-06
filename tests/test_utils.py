# -*- coding: utf-8 -*-

from tornado.httputil import HTTPServerRequest, HTTPHeaders
from unittest import TestCase
from six.moves.urllib.parse import urlparse, parse_qsl
import six

from thr.utils import make_unique_id, serialize_http_request
from thr.utils import unserialize_request_message


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
        (hreq, body_link, http_dict, extra_dict) = \
            unserialize_request_message(msg)
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
        (hreq, body_link, http_dict, extra_dict) = \
            unserialize_request_message(msg)
        self.assertEquals(len(extra_dict), 2)
        self.assertEquals(extra_dict['foo'], "foo1")
        self.assertEquals(extra_dict['bar'], "bar1")

    def test_serialize_body(self):
        uri = "/foo/bar"
        req = HTTPServerRequest(method='PUT', uri=uri, body="foo")
        msg = serialize_http_request(req)
        (hreq, body_link, http_dict, extra_dict) = \
            unserialize_request_message(msg)
        self.assertEquals(hreq.method, 'PUT')
        self.assertEquals(hreq.body.decode(), "foo")
        self.assertEquals(body_link, None)

    def test_serialize_body_link(self):
        uri = "/foo/bar"
        req = HTTPServerRequest(method='PUT', uri=uri)
        msg = serialize_http_request(req, body_link="http://foo.com/bar")
        (hreq, body_link, http_dict, extra_dict) = \
            unserialize_request_message(msg)
        self.assertEquals(hreq.body, None)
        self.assertEquals(body_link, "http://foo.com/bar")

    def test_serialize_headers(self):
        uri = "/foo/bar"
        req = HTTPServerRequest(method='GET', uri=uri)
        headers = HTTPHeaders()
        headers.add("Foo", "bar")
        headers.add("Foo", "bar2")
        headers.add("Foo2", "bar3")
        req.headers = headers
        msg = serialize_http_request(req)
        (hreq, body_link, http_dict, extra_dict) = \
            unserialize_request_message(msg)
        self.assertEquals(len(list(hreq.headers.get_all())), 3)
        self.assertEquals(hreq.headers['Foo2'], "bar3")
        self.assertEquals(hreq.headers['Foo'], "bar,bar2")

    def test_serialize_query_string(self):
        uri = "/foo/bar"
        req = HTTPServerRequest(method='GET', uri=uri)
        utf = u"éééééé"
        bs = utf.encode('utf-8')
        req.query_arguments = {"foo1": [b"bar1", b"bar2"], "foo2": [bs],
                               "foo3": [b"bar3"]}
        msg = serialize_http_request(req)
        (hreq, body_link, http_dict, extra_dict) = \
            unserialize_request_message(msg)
        o = urlparse(hreq.url)
        if six.PY3:
            parsed = sorted(parse_qsl(o.query), key=lambda x: x[0])
        else:
            parsed = sorted(parse_qsl(o.query.encode('ASCII')))
        self.assertEquals(parsed[0][0], 'foo1')
        self.assertEquals(parsed[0][1], 'bar1')
        self.assertEquals(parsed[1][0], 'foo1')
        self.assertEquals(parsed[1][1], 'bar2')
        self.assertEquals(parsed[2][0], 'foo2')
        if six.PY3:
            self.assertEquals(parsed[2][1], utf)
        else:
            self.assertEquals(parsed[2][1], bs)
        self.assertEquals(parsed[3][0], 'foo3')
        self.assertEquals(parsed[3][1], 'bar3')
