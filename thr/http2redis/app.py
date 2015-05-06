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
from thr.http2redis.exchange import HTTPExchange
from thr.utils import make_unique_id, serialize_http_request
from thr import DEFAULT_REDIS_HOST, DEFAULT_REDIS_PORT, DEFAULT_REDIS_QUEUE


define("config", help="Path to config file")
define("port", type=int, default=8888, help="Listening port")
define("redis_host", default=DEFAULT_REDIS_HOST,
       help="Default redis server hostname or ip")
define("redis_port", default=DEFAULT_REDIS_PORT, type=int,
       help="Default redis server port")
define("redis_queue", default=DEFAULT_REDIS_QUEUE,
       help="Default redis queue")

redis_pools = {}


def get_redis_pool(host, port):
    global redis_pools
    key = "%s:%i" % (host, port)
    if key not in redis_pools:
        redis_pools[key] = tornadis.ClientPool()
    return redis_pools[key]


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
        if exchange.response.status_code is not None:
            self.set_status(exchange.response.status_code)
        for name in exchange.response.headers.keys():
            value = exchange.response.headers[name]
            self.set_header(name, value)
        if exchange.response.body is not None:
            self.finish(exchange.response.body)
        else:
            self.finish()

    @gen.coroutine
    def handle(self, *args, **kwargs):
        exchange = HTTPExchange(self.request,
                                default_redis_host=options.redis_host,
                                default_redis_port=options.redis_port,
                                default_redis_queue=options.redis_queue)
        yield Rules.execute_input_actions(exchange)
        if exchange.response.status_code is not None:
            # so we don't push the request on redis
            # let's call output actions for headers and body
            yield Rules.execute_output_actions(exchange)
            self.return_http_reply(exchange)
        elif exchange.redis_queue == "null":
            self.write("404 Not found")
            self.set_status(404)
        else:
            redis_pool = get_redis_pool(exchange.redis_host,
                                        exchange.redis_port)
            with (yield redis_pool.connected_client()) as redis:
                response_key = make_unique_id()
                serialized_request = serialize_http_request(
                    exchange.request,
                    dict_to_inject={
                        'response_key': response_key
                    })
                yield redis.call('LPUSH', exchange.redis_queue,
                                 serialized_request)
                result = yield redis.call('BRPOP', response_key, 1)
                if result:
                    yield Rules.execute_output_actions(exchange)
                    if exchange.response.body is None:
                        exchange.response.body = result[1]
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
