#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from tornado import ioloop
from tornado import gen, httpserver, netutil
from tornado.web import RequestHandler, Application, url
from tornado.options import define, options, parse_command_line
import tornadis
import time
import six
import signal
import functools
import datetime
import logging

from thr.http2redis.rules import Rules
from thr.http2redis.exchange import HTTPExchange
from thr.utils import make_unique_id, serialize_http_request, \
    unserialize_response_message
from thr import DEFAULT_REDIS_HOST, DEFAULT_REDIS_PORT, DEFAULT_REDIS_QUEUE
from thr import DEFAULT_TIMEOUT, REDIS_POOL_CLIENT_TIMEOUT


define("timeout", type=int, help="Timeout in second for a request",
       default=DEFAULT_TIMEOUT)
define("config", help="Path to config file")
define("port", type=int, default=8888, help="Listening port")
define("redis_host", default=DEFAULT_REDIS_HOST,
       help="Default redis server hostname or ip")
define("redis_port", default=DEFAULT_REDIS_PORT, type=int,
       help="Default redis server port")
define("redis_uds", type=str,
       help="Default redis unix socket path")
define("redis_queue", default=DEFAULT_REDIS_QUEUE,
       help="Default redis queue")
define("unix_socket", default=None, help="Path to unix socket to bind")
define("backlog", type=int, default=128, help="socket backlog")

redis_pools = {}
running_exchanges = {}


def get_redis_pool(host=None, port=None, uds=None):
    global redis_pools
    if uds is None:
        key = "%s:%i" % (host, port)
    else:
        key = uds
    if key not in redis_pools:
        kwargs = {"autoclose": True, "connect_timeout": options.timeout,
                  "client_timeout": REDIS_POOL_CLIENT_TIMEOUT,
                  "aggressive_write": True}
        if uds is None:
            kwargs["host"] = host
            kwargs["port"] = port
            kwargs["tcp_nodelay"] = True
        else:
            kwargs["unix_domain_socket"] = uds
        redis_pools[key] = tornadis.ClientPool(**kwargs)
    return redis_pools[key]


class Handler(RequestHandler):

    __request_id = None

    def compute_etag(self, *args, **kwargs):
        return None

    def check_etag_header(self, *args, **kwargs):
        return False

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

    def finish(self, chunk=None):
        global running_exchanges
        if chunk is None or len(chunk) == 0:
            RequestHandler.finish(self)
        else:
            RequestHandler.finish(self, chunk)
        try:
            del(running_exchanges[self.__request_id])
        except KeyError:
            pass

    def return_http_reply(self, exchange, force_status=None, force_body=None):
        status = exchange.response.status_code
        body = exchange.response.body
        if force_status:
            status = force_status
        if force_body:
            body = force_body
        if body is None and exchange.output_default_body is not None and \
                exchange.output_default_body != "null":
            body = exchange.output_default_body
        if status is not None:
            if status == 599:
                self.set_status(504)
            else:
                self.set_status(status)
        for name in exchange.response.headers.keys():
            value = exchange.response.headers[name]
            self.set_header(name, value)
        self.finish(body)

    def update_exchange_from_response_message(self, exchange, message):
        (status_code, body, body_link, headers, _) = \
            unserialize_response_message(message)
        exchange.response.status_code = status_code
        # FIXME: body_link ???
        exchange.response.body = body
        exchange.response.headers = headers

    @gen.coroutine
    def handle(self, *args, **kwargs):
        exchange = HTTPExchange(self.request,
                                default_redis_host=options.redis_host,
                                default_redis_port=options.redis_port,
                                default_redis_queue=options.redis_queue,
                                default_redis_uds=options.redis_uds)
        self.__request_id = exchange.request_id
        running_exchanges[self.__request_id] = exchange
        yield Rules.execute_input_actions(exchange)
        if exchange.response.status_code is not None and \
                exchange.response.status_code != "null":
            # so we don't push the request on redis
            # let's call output actions for headers and body
            yield Rules.execute_output_actions(exchange)
            self.return_http_reply(exchange)
        elif exchange.redis_queue == "null":
            # so we don't push the request on redis
            # let's call output actions for headers and body
            yield Rules.execute_output_actions(exchange)
            self.return_http_reply(exchange, force_status=404,
                                   force_body="no redis queue set")
        else:
            redis_pool = get_redis_pool(host=exchange.redis_host,
                                        port=exchange.redis_port,
                                        uds=exchange.redis_uds)
            with (yield redis_pool.connected_client()) as redis:
                response_key = "thr:queue:response:%s" % make_unique_id()
                serialized_request = serialize_http_request(
                    exchange.request,
                    dict_to_inject={
                        'response_key': response_key,
                        'priority': exchange.priority,
                        'creation_time': time.time(),
                        'request_id': exchange.request_id
                    })
                lpush_res = yield redis.call('LPUSH', exchange.redis_queue,
                                             serialized_request)
                if not isinstance(lpush_res, six.integer_types):
                    yield Rules.execute_output_actions(exchange)
                    self.return_http_reply(exchange, force_status=500,
                                           force_body="can't connect to bus")
                    return

                before = datetime.datetime.now()
                while True:
                    result = yield redis.call('BRPOP', response_key, 1)
                    if not isinstance(result, tornadis.ConnectionError):
                        self.update_exchange_from_response_message(exchange,
                                                                   result[1])
                        yield Rules.execute_output_actions(exchange)
                        self.return_http_reply(exchange)
                        break
                    after = datetime.datetime.now()
                    delta = after - before
                    if delta.total_seconds() > options.timeout:
                        yield Rules.execute_output_actions(exchange)
                        self.return_http_reply(exchange, force_status=504,
                                               force_body="no reply from "
                                               "the backend")
                        break


def make_app():
    if options.config is not None:
        exec(open(options.config).read(), {})
    return Application([url(r"/.*", Handler)])


def sig_handler(server, sig, frame):
    logging.warning('Caught signal: %s', sig)
    ioloop.IOLoop.instance().add_callback_from_signal(shutdown, server)


def shutdown(server):
    logging.info('Stopping http server')
    server.stop()
    logging.info('Will shutdown in (max) %s seconds...', options.timeout)
    io_loop = ioloop.IOLoop.instance()
    deadline = time.time() + options.timeout

    def stop_loop():
        now = time.time()
        if now < deadline and len(running_exchanges) > 0:
            io_loop.add_timeout(now + 1, stop_loop)
        else:
            io_loop.stop()
            logging.info('Shutdown')
    stop_loop()


def main():
    parse_command_line()
    print("Start http2redis on http://localhost:{}".format(options.port))
    app = make_app()
    server = httpserver.HTTPServer(app)
    if options.unix_socket:
        socket = netutil.bind_unix_socket(options.unix_socket,
                                          backlog=options.backlog)
        server.add_socket(socket)
    if options.port != 0:
        sockets = netutil.bind_sockets(options.port,
                                       backlog=options.backlog)
        server.add_sockets(sockets)
    signal.signal(signal.SIGTERM, functools.partial(sig_handler, server))
    ioloop.IOLoop.instance().set_blocking_log_threshold(1)
    ioloop.IOLoop.instance().start()
