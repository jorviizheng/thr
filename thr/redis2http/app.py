#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import tornado
import time
import json
import functools
from six.moves import queue as _queue
from tornado.options import define, options, parse_command_line
import tornadis
import toro
import six
import logging
import signal
import os
from datetime import timedelta, datetime

from thr.redis2http.limits import Limits
from thr.redis2http.exchange import HTTPRequestExchange
from thr.redis2http.queue import Queues
from thr.redis2http.counter import incr_counters, decr_counters
from thr.redis2http.counter import get_counter
from thr.utils import serialize_http_response, timedelta_total_ms
from thr import DEFAULT_TIMEOUT, DEFAULT_LOCAL_QUEUE_MAX_SIZE
from thr import DEFAULT_MAXIMUM_LIFETIME, BRPOP_TIMEOUT
from thr import DEFAULT_MAXIMUM_LOCAL_QUEUE_LIFETIME_MS

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
define("max_local_queue_lifetime_ms", help="Maximum lifetime (in ms) for a "
       "request on local queue before reuploading on bus", type=int,
       default=DEFAULT_MAXIMUM_LOCAL_QUEUE_LIFETIME_MS)
define("stats_file", type=str, help="Complete path of the json stat file",
       default="/tmp/redis2http_stats.json")
define("stats_frequency_ms", type=int, help="Stats file write frequency "
       "(in ms) (0 => no stats write)", default=2000)

redis_pools = {}
request_queue = None
running_request_redis_handler_number = 0
running_bus_reinject_handler_number = 0
total_request_counter = 0
expired_request_counter = 0
local_reinject_counter = 0
bus_reinject_counter = 0

# stopping mode
# (0 => not stopping, 1 => stopping request_redis_handler,
#  2 => stopping local_queue_handler, 3 => stopping local_reinject_handler
#  4 => stopping bus_reinject_handlers, 5 => finishing running exchanges,
#  6 => stopped)
stopping = 0

reinject_event = toro.Event()
local_reinject_queue = toro.PriorityQueue()
bus_reinject_queues = {}
running_exchanges = {}

logger = logging.getLogger("thr.redis2http")

async_client_impl = "tornado.simple_httpclient.SimpleAsyncHTTPClient"
tornado.httpclient.AsyncHTTPClient.configure(async_client_impl,
                                             max_clients=100000)


def get_bus_reinject_queue(host, port):
    global bus_reinject_queues
    key = "%s:%i" % (host, port)
    if key not in bus_reinject_queues:
        bus_reinject_queues[key] = toro.PriorityQueue()
    return bus_reinject_queues[key]


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


def get_redis_client(host, port):
    return tornadis.Client(host=host, port=port, return_connection_error=True,
                           connect_timeout=options.timeout,
                           autoconnect=True)


@tornado.gen.coroutine
def request_redis_handler(queue, single_iteration=False):
    global expired_request_counter
    redis = get_redis_client(queue.host, queue.port)
    while stopping < 1:
        tmp = yield redis.call('BRPOP', queue.queue, BRPOP_TIMEOUT)
        if isinstance(tmp, tornadis.ConnectionError):
            logger.warning("connection error while brpoping queue "
                           "redis://%s:%i/%s => sleeping 5s and retrying",
                           queue.host, queue.port, queue.queue)
            yield tornado.gen.sleep(5)
            continue
        if tmp:
            _, request = tmp
            rq = get_request_queue()
            exchange = HTTPRequestExchange(request, queue)
            lifetime = exchange.lifetime()
            rid = exchange.request_id
            if lifetime > options.max_lifetime:
                logger.warning("expired request #%s (lifetime: %i) got from "
                               "queue redis://%s:%i/%s => trash it", rid,
                               lifetime, queue.host, queue.port, queue.queue)
                expired_request_counter += 1
                continue
            priority = exchange.priority
            logger.debug("Got request #%s (lifetime: %i) got from "
                         "queue redis://%s:%i/%s => local queue it "
                         "with priority: %i", rid, lifetime, queue.host,
                         queue.port, queue.queue, priority)
            yield rq.put((priority, exchange))
        if single_iteration:
            break
    logger.info("request_redis_handler redis://%s:%i/%s stopped", queue.host,
                queue.port, queue.queue)


@tornado.gen.coroutine
def process_request(exchange, hashes):
    global running_exchanges
    async_client = tornado.httpclient.AsyncHTTPClient()
    request = exchange.request
    request.connect_timeout = options.timeout
    request.request_timeout = options.timeout
    request.decompress_response = False
    request.follow_redirects = False
    response_key = exchange.extra_dict['response_key']
    queue = exchange.queue
    rid = exchange.request_id
    logger.info("Calling %s on %s (#%s)....", request.method, request.url, rid)
    before = datetime.now()
    running_exchanges[rid] = (before, exchange)
    redirection = 0
    while redirection < 10:
        response = yield async_client.fetch(request, raise_error=False)
        location = response.headers.get('Location', None)
        if response.headers.get('X-Thr-FollowRedirects', "0") == "1" and \
                response.code in (301, 302, 307, 308) and location:
            # redirection
            logger.debug("internal redirection => %s", location)
            request.url = location
            redirection += 1
            continue
        break
    if redirection >= 10:
        response = tornado.httpclient.HTTPResponse(request, 310)
    after = datetime.now()
    dt = after - before
    logger.debug("Got a reply #%i after %i ms (#%s)", response.code,
                 timedelta_total_ms(dt), rid)
    redis_pool = get_redis_pool(queue.host, queue.port)
    pipeline = tornadis.Pipeline()
    pipeline.stack_call("LPUSH", response_key,
                        serialize_http_response(response))
    pipeline.stack_call("EXPIRE", response_key, options.timeout)
    with (yield redis_pool.connected_client()) as redis:
        yield redis.call(pipeline)
    del(running_exchanges[rid])


def decr_counters_callback(hashes, future):
    global total_request_counter
    decr_counters(hashes)
    reinject_event.set()
    total_request_counter += 1


@tornado.gen.coroutine
def local_reinject_handler(single_iteration=False):
    global stopping
    mlqlms = options.max_local_queue_lifetime_ms
    deadline_us = timedelta(microseconds=(mlqlms * 1000))
    while stopping < 3:
        try:
            yield reinject_event.wait(deadline=deadline_us)
        except toro.Timeout:
            pass
        while True:
            try:
                priority, exchange = local_reinject_queue.get_nowait()
                rid = exchange.request_id
                if stopping >= 3:
                    logger.debug("stopping => reinject #%s on bus", rid)
                    host, port = exchange.queue.host, exchange.queue.port
                    get_bus_reinject_queue(host, port).put_nowait((priority,
                                                                   exchange))
                    continue
                if exchange.lifetime_in_local_queue_ms() > mlqlms:
                    logger.debug("request #%s reached max lifetime on local "
                                 "queue: %i ms => scheduling reinject on bus",
                                 rid, exchange.lifetime_in_local_queue_ms)
                    host, port = exchange.queue.host, exchange.queue.port
                    get_bus_reinject_queue(host, port).put_nowait((priority,
                                                                   exchange))
                    continue
                try:
                    get_request_queue().put_nowait((exchange.priority,
                                                    exchange))
                    logger.debug("reinjected request #%s on local queue", rid)
                except _queue.Full:
                    logger.debug("can't reinject request #%s on local queue "
                                 "(full) => scheduling reinject on bus", rid)
                    host, port = exchange.queue.host, exchange.queue.port
                    get_bus_reinject_queue(host, port).put_nowait((priority,
                                                                   exchange))
            except _queue.Empty:
                reinject_event.clear()
                break
        if single_iteration:
            break
    logger.info("local_reinject_handler stopped")


@tornado.gen.coroutine
def bus_reinject_handler(host, port, single_iteration=False):
    global bus_reinject_counter
    redis = get_redis_client(host, port)
    queue = get_bus_reinject_queue(host, port)
    deadline = timedelta(seconds=3)
    while True:
        if stopping >= 4 and queue.qsize() == 0:
            break
        try:
            priority, exchange = yield queue.get(deadline=deadline)
        except toro.Timeout:
            continue
        rid = exchange.request_id
        logger.debug("reinject request #%s on redis://%s:%i/%s", rid, host,
                     port, exchange.queue.queue)
        result = yield redis.call('LPUSH', exchange.queue.queue,
                                  exchange.serialized_request)
        if not isinstance(result, six.integer_types):
            logger.warning("can't reinject request #%s on redis://%s:%i/%s "
                           "=> sleeping 5s and re-queueing the request",
                           rid, host, port, exchange.queue.queue)
            yield tornado.gen.sleep(5)
            queue.put_nowait((priority, exchange))
        else:
            bus_reinject_counter += 1
        if single_iteration:
            break
    logger.info("bus_reinject_handler redis://%s:%i stopped", host, port)


@tornado.gen.coroutine
def local_queue_handler(single_iteration=False):
    global expired_request_counter, local_reinject_counter
    deadline = timedelta(seconds=3)
    while stopping < 2:
        try:
            priority, exchange = \
                yield get_request_queue().get(deadline=deadline)
        except toro.Timeout:
            continue
        rid = exchange.request_id
        lifetime = exchange.lifetime()
        if lifetime > options.max_lifetime:
            logger.warning("expired request #%s (lifetime: %i) got from "
                           "local queue => trash it", rid, lifetime)
            expired_request_counter += 1
            continue
        hashes = Limits.check(exchange.request)
        if hashes is None:
            local_reinject_queue.put((priority, exchange))
            local_reinject_counter += 1
        else:
            # The request has been accepted, increment the counters now
            incr_counters(hashes)
            future = process_request(exchange, hashes)
            cb = functools.partial(decr_counters_callback, hashes)
            tornado.ioloop.IOLoop.instance().add_future(future, cb)
        if single_iteration:
            break
    logger.info("local_queue_handler stopped")


def write_stats():
    stats = {"epoch": time.time(), "stopping_mode": stopping}
    stats["request_queue_size"] = get_request_queue().qsize()
    stats["local_reinject_queue_size"] = local_reinject_queue.qsize()
    for key, queue in bus_reinject_queues.items():
        stats["bus_reinject_queue_%s_size" % key] = queue.qsize()
    running_requests = {}
    now = datetime.now()
    for key, tmp in running_exchanges.items():
        before, exchange = tmp
        running_requests[key] = {"method": exchange.request.method,
                                 "url": exchange.request.url,
                                 "since_ms": timedelta_total_ms(now - before)}
    stats["running_requests"] = running_requests
    stats["running_bus_reinject_handler_number"] = \
        running_bus_reinject_handler_number
    stats["running_request_redis_handler_number"] = \
        running_request_redis_handler_number
    stats['local_reinject_counter'] = local_reinject_counter
    stats['bus_reinject_counter'] = bus_reinject_counter
    stats['total_request_counter'] = total_request_counter
    stats['expired_request_counter'] = expired_request_counter
    stats['counters'] = {}
    for name, limit in six.iteritems(Limits.limits):
        if limit.show_in_stats:
            stats['counters'][name + "_limit"] = limit.limit
            stats['counters'][name + "_value"] = get_counter(name)
    with open(options.stats_file, "w") as f:
        f.write(json.dumps(stats, indent=4))


def stop_loop(future):
    exc = future.exception()
    if exc is not None:
        raise exc
    _stop_loop()


def _stop_loop():
    global running_request_redis_handler_number, stopping,\
        running_bus_reinject_handler_number
    if stopping == 0:
        tornado.ioloop.IOLoop.instance().stop()
    else:
        if stopping == 1:
            running_request_redis_handler_number -= 1
            if running_request_redis_handler_number == 0:
                stopping += 1
        elif stopping == 4:
            running_bus_reinject_handler_number -= 1
            if running_bus_reinject_handler_number == 0:
                stopping += 1
                tornado.ioloop.IOLoop.instance().call_later(1, _stop_loop)
        elif stopping == 5:
            if len(running_exchanges) == 0:
                logger.info("stopping ioloop...")
                tornado.ioloop.IOLoop.instance().stop()
            else:
                logger.info("waiting for %i request(s) to finish...",
                            len(running_exchanges))
                tornado.ioloop.IOLoop.instance().call_later(1, _stop_loop)
        else:
            stopping += 1


def sig_handler(sig, frame):
    logging.info('caught signal: %s', sig)
    tornado.ioloop.IOLoop.instance().add_callback_from_signal(shutdown)


def shutdown():
    global stopping
    stopping = 1
    reinject_event.set()


def main():
    global running_request_redis_handler_number,\
        running_bus_reinject_handler_number
    parse_command_line()
    if options.config is not None:
        exec(open(options.config).read(), {})
    loop = tornado.ioloop.IOLoop.instance()
    launched_bus_reinject_handlers = {}
    for queue in Queues:
        host = queue.host
        port = queue.port
        workers = queue.workers
        for i in range(0, workers):
            loop.add_future(request_redis_handler(queue), stop_loop)
            running_request_redis_handler_number += 1
        if "%s:%i" % (host, port) not in launched_bus_reinject_handlers:
            loop.add_future(bus_reinject_handler(host, port), stop_loop)
            launched_bus_reinject_handlers["%s:%i" % (host, port)] = True
            running_bus_reinject_handler_number += 1
    loop.add_future(local_reinject_handler(), stop_loop)
    loop.add_future(local_queue_handler(), stop_loop)
    if options.stats_frequency_ms > 0:
        stats_pc = tornado.ioloop.PeriodicCallback(write_stats,
                                                   options.stats_frequency_ms)
        stats_pc.start()
    signal.signal(signal.SIGTERM, sig_handler)
    tornado.ioloop.IOLoop.instance().add_callback(logger.info,
                                                  "redis2http started")
    loop.start()
    try:
        os.remove(options.stats_file)
    except:
        pass
    logger.info("redis2http stopped")
