#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import tornado
import functools
from six.moves import queue as _queue
from tornado.options import define, options, parse_command_line
import tornadis
import toro
import logging

from thr.redis2http.limits import Limits
from thr.redis2http.exchange import HTTPRequestExchange
from thr.redis2http.queue import Queues
from thr.redis2http.counter import incr_counters, decr_counters
from thr.utils import serialize_http_response
from thr import DEFAULT_TIMEOUT, DEFAULT_LOCAL_QUEUE_MAX_SIZE
from thr import DEFAULT_MAXIMUM_LIFETIME, BRPOP_TIMEOUT

try:
    define("config", help="Path to config file")
    define("timeout", type=int, help="Timeout in second for a request",
           default=DEFAULT_TIMEOUT)
except:
    # already defined (probably because we are launching unit tests)
    pass
define("local_queue_max_size", help="Local queue (in process) max size",
       type=int, default=DEFAULT_LOCAL_QUEUE_MAX_SIZE)
define("max_lifetime", help="Maximum lifetime (in second) for a request on "
       "buses/queues", type=int, default=DEFAULT_MAXIMUM_LIFETIME)

redis_pools = {}
request_queue = None

reinject_event = toro.Event()
local_reinject_queue = toro.Queue()
bus_reinject_queue = toro.Queue()

logger = logging.getLogger("thr.redis2http")

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
    redis = tornadis.Client(host=queue.host, port=queue.port,
                            connect_timeout=options.timeout,
                            autoconnect=True)
    while True:
        tmp = yield redis.call('BRPOP', queue.queue, BRPOP_TIMEOUT)
        if tmp:
            _, request = tmp
            rq = get_request_queue()
            exchange = HTTPRequestExchange(request, queue)
            lifetime = exchange.lifetime()
            if lifetime > options.max_lifetime:
                logger.warning("expired request (lifetime: %i) got from "
                               "queue redis://%s:%i/%s => trash it",
                               lifetime, queue.host, queue.port, queue.queue)
            else:
                priority = exchange.priority
                logger.debug("Got request (lifetime: %i) got from "
                             "queue redis://%s:%i/%s => local queue it "
                             "with priority: %i",
                             lifetime, queue.host, queue.port, queue.queue,
                             priority)
                yield rq.put((priority, exchange))
        if single_iteration:
            break


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
    reinject_event.set()


@tornado.gen.coroutine
def local_reinject_handler(single_iteration=False):
    while True:
        yield reinject_event.wait()
        while True:
            try:
                exchange = local_reinject_queue.get_nowait()
                try:
                    get_request_queue().put_nowait((exchange.priority,
                                                    exchange))
                    logger.debug("reinjected request on local queue")
                except _queue.Full:
                    logger.debug("can't reinject request on local queue (full)"
                                 " => scheduling reinject on bus")
                    bus_reinject_queue.put_nowait(exchange)
            except _queue.Empty:
                reinject_event.clear()
                break
        if single_iteration:
            break


@tornado.gen.coroutine
def bus_reinject_handler(single_iteration=False):
    while True:
        exchange = yield bus_reinject_queue.get()
        redis_request_pool = get_redis_pool(exchange.queue.host,
                                            exchange.queue.port)
        with (yield redis_request_pool.connected_client()) as redis:
            logger.debug("reinject request on redis://%s:%i/%s",
                         exchange.queue.host, exchange.queue.port,
                         exchange.queue.queue)
            yield redis.call('LPUSH', exchange.queue.queue,
                             exchange.serialized_request)
        if single_iteration:
            break


@tornado.gen.coroutine
def local_queue_handler(single_iteration=False):
    """
    Get a request for the toro queue, check the limits for each hash,
    and process the request if there is a free worker
    """
    while True:
        priority, exchange = yield get_request_queue().get()
        hashes = Limits.check(exchange.request)
        if hashes is None:
            local_reinject_queue.put(exchange)
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
    loop.add_future(bus_reinject_handler(), stop_loop)
    loop.add_future(local_reinject_handler(), stop_loop)
    loop.add_future(local_queue_handler(), stop_loop)
    loop.start()
