#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from tornado import ioloop
from tornado import gen
from tornado.web import RequestHandler, Application, url
from tornado.options import define, options, parse_command_line
import tornadis

from thr.http2redis.rules import Rules
from thr.http2redis import HTTPExchange
from thr.utils import make_unique_id, serialize_http_request


redis_pool = tornadis.ClientPool()


define("config", help="Path to config file")
define("port", type=int, default=8888, help="Server port")


class Handler(RequestHandler):

    def get(self, *args, **kwargs):
        return self.handle(*args, **kwargs)

    def post(self, *args, **kwargs):
        return self.handle(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return self.handle(*args, **kwargs)

    def put(self, *args, **kwargs):
        return self.handle(*args, **kwargs)

    def head(self, *args, **kwargs):
        return self.handle(*args, **kwargs)

    def options(self, *args, **kwargs):
        return self.handle(*args, **kwargs)

    def patch(self, *args, **kwargs):
        return self.handle(*args, **kwargs)

    def return_http_reply(self, exchange):
        status_code = exchange.response.get('status_code', 200)
        self.set_status(status_code)
        if 'headers' in exchange.response:
            for name in exchange.response['headers'].keys():
                value = exchange.response['headers'][name]
                self.set_header(name, value)
        if 'body' in exchange.response:
            self.finish(exchange.response['body'])
        else:
            self.finish()

    @gen.coroutine
    def handle(self, *args, **kwargs):
        exchange = HTTPExchange(self.request)
        yield Rules.execute_input_actions(exchange)
        if 'status_code' in exchange.response:
            # so we don't push the request on redis
            # let's call output actions for headers and body
            yield Rules.execute_output_actions(exchange)
            self.return_http_reply(exchange)
        elif exchange.queue is None:
            self.write("404 Not found")
            self.set_status(404)
        else:
            with (yield redis_pool.connected_client()) as redis:
                response_key = make_unique_id()
                serialized_request = serialize_http_request(
                    exchange.request,
                    dict_to_inject={
                        'response_key': response_key
                    })
                yield redis.call('LPUSH', exchange.queue, serialized_request)
                result = yield redis.call('BRPOP', response_key, 1)
                if result:
                    yield Rules.execute_output_actions(exchange)
                    if 'body' not in exchange.response:
                        exchange.response['body'] = result[1]
                    self.return_http_reply(exchange)


def make_app():
    if options.config is not None:
        exec(open(options.config).read(), {})
    return Application([url(r"/.*", Handler)])


def main():
    parse_command_line()
    print("Start http2redis on http://localhost:{}".format(options.port))
    app = make_app()
    app.listen(options.port)
    ioloop.IOLoop.instance().start()
