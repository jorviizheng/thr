from tornado.httputil import HTTPServerRequest, HTTPHeaders
from tornado import gen
from tornado.testing import AsyncTestCase, gen_test

from thr.http2redis.exchange import HTTPExchange
from thr.http2redis.rules import Actions


class TestActions(AsyncTestCase):

    def test_set_input_header(self):
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_input_header=('Header-Name', 'header value'))
        actions.execute_input_actions(exchange)
        self.assertEqual(exchange.request.headers['Header-Name'],
                         'header value')

    def test_set_output_header(self):
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_output_header=('Header-Name', 'header value'))
        actions.execute_output_actions(exchange)
        self.assertEqual(exchange.response.headers['Header-Name'],
                         'header value')

    def test_set_status_code(self):
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_status_code=201)
        actions.execute_input_actions(exchange)
        self.assertEqual(exchange.response.status_code, 201)

    def test_set_status_code_with_callable(self):
        def callback(request):
            return 201
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_status_code=callback)
        actions.execute_input_actions(exchange)
        self.assertEqual(exchange.response.status_code, 201)

    def test_queue_with_callable(self):
        def callback(request):
            return 'test-queue'
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_queue=callback)
        actions.execute_input_actions(exchange)
        self.assertEqual(exchange.queue, 'test-queue')

    def test_set_input_header_with_callable(self):
        def callback(request):
            return ('Header-Name', 'header value')
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_input_header=callback)
        actions.execute_input_actions(exchange)
        self.assertEqual(request.headers['Header-Name'], 'header value')

    @gen_test
    def test_set_status_code_with_coroutine(self):
        @gen.coroutine
        def callback(request):
            yield gen.maybe_future(None)
            raise gen.Return(201)
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_status_code=callback)
        yield actions.execute_input_actions(exchange)
        self.assertEqual(exchange.response.status_code, 201)

    def test_add_input_header(self):
        headers = HTTPHeaders()
        headers.add("Header-Name", "header value1")
        request = HTTPServerRequest(method='GET', uri='/', headers=headers)
        exchange = HTTPExchange(request)
        actions = Actions(add_input_header=("Header-Name", "header value2"))
        actions.execute_input_actions(exchange)
        values = exchange.request.headers.get_list('Header-Name')
        self.assertEquals(len(values), 2)
        self.assertEquals(values[0], "header value1")
        self.assertEquals(values[1], "header value2")

    def test_add_output_header(self):
        headers = HTTPHeaders()
        headers.add("Header-Name", "header value1")
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        exchange.response.headers = headers
        actions = Actions(add_output_header=("Header-Name", "header value2"))
        actions.execute_output_actions(exchange)
        values = exchange.response.headers.get_list('Header-Name')
        self.assertEquals(len(values), 2)
        self.assertEquals(values[0], "header value1")
        self.assertEquals(values[1], "header value2")

    def test_del_input_header(self):
        headers = HTTPHeaders()
        headers.add("Header-Name", "header value1")
        request = HTTPServerRequest(method='GET', uri='/', headers=headers)
        exchange = HTTPExchange(request)
        actions = Actions(del_input_header="Header-Name")
        actions.execute_input_actions(exchange)
        keys = list(exchange.request.headers.keys())
        self.assertEquals(len(keys), 0)
        actions = Actions(del_input_header="Header-Name2")
        actions.execute_input_actions(exchange)

    def test_del_output_header(self):
        headers = HTTPHeaders()
        headers.add("Header-Name", "header value1")
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        exchange.response.headers = headers
        actions = Actions(del_output_header="Header-Name")
        actions.execute_output_actions(exchange)
        keys = list(exchange.response.headers.keys())
        self.assertEquals(len(keys), 0)
        actions = Actions(del_output_header="Header-Name2")
        actions.execute_output_actions(exchange)

    def test_set_path(self):
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_path="/foo")
        actions.execute_input_actions(exchange)
        self.assertEqual(exchange.request.path, "/foo")

    def test_set_method(self):
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_method="POST")
        actions.execute_input_actions(exchange)
        self.assertEqual(exchange.request.method, "POST")

    def test_set_host(self):
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_host="foobar:8080")
        actions.execute_input_actions(exchange)
        self.assertEqual(exchange.request.host, "foobar:8080")

    def test_set_remote_ip(self):
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_remote_ip="1.2.3.4")
        actions.execute_input_actions(exchange)
        self.assertEqual(exchange.request.remote_ip, "1.2.3.4")

    def test_set_input_body(self):
        request = HTTPServerRequest(method='PUT', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_input_body=b"foobar")
        actions.execute_input_actions(exchange)
        self.assertEqual(exchange.request.body, b"foobar")

    def test_set_output_body(self):
        request = HTTPServerRequest(method='GET', uri='/')
        exchange = HTTPExchange(request)
        actions = Actions(set_output_body=b"foobar")
        actions.execute_output_actions(exchange)
        self.assertEqual(exchange.response.body, b"foobar")

    def test_set_query_string(self):
        request = HTTPServerRequest(method='GET', uri='/?foo1=bar1')
        exchange = HTTPExchange(request)
        actions = Actions(set_query_string="foo2=bar2&foo3=bar3")
        actions.execute_input_actions(exchange)
        args = exchange.request.query_arguments
        self.assertEqual(len(args), 2)
        self.assertEqual(len(args["foo2"]), 1)
        self.assertEqual(len(args["foo3"]), 1)
        self.assertEqual(args["foo2"][0], b"bar2")
        self.assertEqual(args["foo3"][0], b"bar3")

    def test_add_query_string_arg(self):
        request = HTTPServerRequest(method='GET', uri='/?foo1=bar1')
        exchange = HTTPExchange(request)
        actions = Actions(add_query_string_arg=("foo2", b"bar2"))
        actions.execute_input_actions(exchange)
        args = exchange.request.query_arguments
        self.assertEqual(len(args), 2)
        self.assertEqual(len(args["foo1"]), 1)
        self.assertEqual(len(args["foo2"]), 1)
        self.assertEqual(args["foo1"][0], b"bar1")
        self.assertEqual(args["foo2"][0], b"bar2")

    def test_set_query_string_arg(self):
        request = HTTPServerRequest(method='GET', uri='/?foo1=bar1')
        exchange = HTTPExchange(request)
        actions = Actions(set_query_string_arg=("foo1", b"bar2"))
        actions.execute_input_actions(exchange)
        args = exchange.request.query_arguments
        self.assertEqual(len(args), 1)
        self.assertEqual(len(args["foo1"]), 1)
        self.assertEqual(args["foo1"][0], b"bar2")

    def test_del_query_string_arg(self):
        request = HTTPServerRequest(method='GET', uri='/?foo1=bar1')
        exchange = HTTPExchange(request)
        actions = Actions(del_query_string_arg="foo1")
        actions.execute_input_actions(exchange)
        args = exchange.request.query_arguments
        self.assertEqual(len(args), 0)
        actions = Actions(del_query_string_arg="foo2")
        actions.execute_input_actions(exchange)
