#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import tornado
import functools
import Queue
from tornado.options import define, options, parse_command_line
import tornadis
import toro

from thr.redis2http.limits import Limits
from thr.redis2http.exchange import HTTPRequestExchange
from thr.redis2http.queue import Queues
from thr.redis2http.counter import incr_counters, decr_counters
from thr.utils import serialize_http_response
from thr import DEFAULT_TIMEOUT, DEFAULT_LOCAL_QUEUE_MAX_SIZE

try:
    define("config", help="Path to config file")
    define("timeout", type=int, help="Timeout in second for a request",
           default=DEFAULT_TIMEOUT)
except:
    # already defined (probably because we are launching unit tests)
    pass
define("local_queue_max_size", help="Local queue (in process) max size",
       type=int, default=DEFAULT_LOCAL_QUEUE_MAX_SIZE)

redis_pools = {}
request_queue = None

async_client_impl = "tornado.simple_httpclient.SimpleAsyncHTTPClient"
tornado.httpclient.AsyncHTTPClient.configure(async_client_impl,
                                             max_clients=100000)


def get_request_queue():
    global request_queue
    if request_queue is None:
        request_queue = toro.PriorityQueue(options.local_queue_max_size)
    return request_queue


def get_redis_pool(host, port):
    global redis_pools
    key = "%s:%i" % (host, port)
    if key not in redis_pools:
        redis_pools[key] = \
            tornadis.ClientPool(host=host, port=port,
                                connect_timeout=options.timeout)
    return redis_pools[key]


@tornado.gen.coroutine
def request_redis_handler(queue, single_iteration=False):
    loop = True
    while loop:
        if single_iteration:
            loop = False
        redis_request_pool = get_redis_pool(queue.host, queue.port)
        with (yield redis_request_pool.connected_client()) as redis:
            tmp = yield redis.call('BRPOP', queue.queue, 10)
            if tmp:
                _, request = tmp
                rq = get_request_queue()
                exchange = HTTPRequestExchange(request, queue)
                priority = exchange.priority
                yield rq.put((priority, exchange))


@tornado.gen.coroutine
def process_request(exchange, hashes):
    """
    Update the workers counters for each hash and send the request to a worker
    """
    async_client = tornado.httpclient.AsyncHTTPClient()
    request = exchange.request
    request.connect_timeout = options.timeout
    request.request_timeout = options.timeout
    response_key = exchange.extra_dict['response_key']
    queue = exchange.queue
    response = yield async_client.fetch(request, raise_error=False)
    redis_request_pool = get_redis_pool(queue.host, queue.port)
    with (yield redis_request_pool.connected_client()) as redis:
        yield redis.call('LPUSH', response_key,
                         serialize_http_response(response))


def decr_counters_callback(hashes, future):
    decr_counters(hashes)


def reinject_callback(exchange):
    try:
        # FIXME: config
        if exchange.lifetime_ms() <= 1000:
            get_request_queue().put_nowait((exchange.priority, exchange))
            return
    except Queue.Full:
        pass
    future = reinject_on_bus(exchange)
    tornado.ioloop.IOLoop.instance().add_future(future, lambda x: None)


@tornado.gen.coroutine
def reinject_on_bus(exchange):
    redis_request_pool = get_redis_pool(exchange.queue.host,
                                        exchange.queue.port)
    with (yield redis_request_pool.connected_client()) as redis:
        yield redis.call('LPUSH', exchange.queue.queue,
                         exchange.serialized_request)


@tornado.gen.coroutine
def request_toro_handler(single_iteration=False):
    """
    Get a request for the toro queue, check the limits for each hash,
    and process the request if there is a free worker
    """
    while True:
        priority, exchange = yield get_request_queue().get()
        hashes = Limits.check(exchange.request)
        if hashes is None:
            # Request rejected, we will re add to the queue at the end
            # FIXME: conf
            tornado.ioloop.IOLoop.instance().call_later(0.01,
                                                        reinject_callback,
                                                        exchange)
        else:
            # The request has been accepted, increment the counters now
            incr_counters(hashes)
            future = process_request(exchange, hashes)
            cb = functools.partial(decr_counters_callback, hashes)
            tornado.ioloop.IOLoop.instance().add_future(future, cb)
        if single_iteration:
            break


def stop_loop(future):
    exc = future.exception()
    if exc is not None:
        raise exc
    tornado.ioloop.IOLoop.instance().stop()


def main():
    parse_command_line()
    if options.config is not None:
        exec(open(options.config).read(), {})
    loop = tornado.ioloop.IOLoop.instance()
    for queue in Queues:
        loop.add_future(request_redis_handler(queue), stop_loop)
        loop.add_future(request_redis_handler(queue), stop_loop)
        loop.add_future(request_redis_handler(queue), stop_loop)
    loop.add_future(request_toro_handler(), stop_loop)
    loop.start()
