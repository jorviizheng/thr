#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import tornado
import time
import functools
import json
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
from thr.redis2http.counter import decr_counters
from thr.redis2http.counter import get_counter, get_counter_blocks
from thr.redis2http.counter import get_global_counter_name
from thr.redis2http.counter import conditional_incr_counters
from thr.utils import serialize_http_response, timedelta_total_ms
from thr.utils import UnixResolver, format_future_exception
from thr import DEFAULT_TIMEOUT
from thr import DEFAULT_MAXIMUM_LIFETIME, BRPOP_TIMEOUT
from thr import DEFAULT_MAXIMUM_LOCAL_QUEUE_LIFETIME_MS
from thr import DEFAULT_BLOCKED_QUEUE_MAX_SIZE
from thr import REDIS_POOL_CLIENT_TIMEOUT

try:
    define("config", help="Path to config file")
    define("timeout", type=int, help="Timeout in second for a request",
           default=DEFAULT_TIMEOUT)
except:
    # already defined (probably because we are launching unit tests)
    pass
define("max_lifetime", help="Maximum lifetime (in second) for a request on "
       "buses/queues", type=int, default=DEFAULT_MAXIMUM_LIFETIME)
define("blocked_queue_max_size", help="Blocked queue (in process) max size",
       type=int, default=DEFAULT_BLOCKED_QUEUE_MAX_SIZE)
define("max_local_queue_lifetime_ms", help="Maximum lifetime (in ms) for a "
       "request on local queue before reuploading on bus (min precision "
       "100ms)", type=int, default=DEFAULT_MAXIMUM_LOCAL_QUEUE_LIFETIME_MS)
define("stats_file", type=str, help="Complete path of the json stat file",
       default="/tmp/redis2http_stats.json")
define("stats_frequency_ms", type=int, help="Stats file write frequency "
       "(in ms) (0 => no stats write)", default=2000)
define("add_thr_extra_headers", type=bool, default=False,
       help="Add X-Thr-* extra headers")

redis_pools = {}
running_request_redis_handler_number = 0
running_bus_reinject_handler_number = 0
total_request_counter = 0
expired_request_counter = 0
bus_reinject_counter = 0

# stopping mode
# (0 => not stopping, 1 => stopping request_redis_handler,
#  2 => stopping expiration_handler
#  3 => finishing running exchanges, 4 = stopping bus_reinject_handlers
#  5 => stopped)
stopping = 0

bus_reinject_queues = {}
running_exchanges = {}
blocked_exchanges = {}
blocked_queues = {}

logger = logging.getLogger("thr.redis2http")

async_client_impl = "tornado.simple_httpclient.SimpleAsyncHTTPClient"
resolver = UnixResolver(resolver=tornado.netutil.Resolver())
tornado.httpclient.AsyncHTTPClient.configure(async_client_impl,
                                             max_clients=100000,
                                             resolver=resolver)


def blocked_queue_put_nowait(counter_name, priority, exchange):
    global blocked_queues
    if counter_name not in blocked_queues:
        blocked_queues[counter_name] = \
            toro.PriorityQueue(options.blocked_queue_max_size)
    blocked_queues[counter_name].put_nowait((priority, exchange))


def blocked_queue_get_nowait(counter_name):
    global blocked_queues
    if counter_name not in blocked_queues:
        raise _queue.Empty()
    return blocked_queues[counter_name].get_nowait()


def get_blocked_queue_size(counter_name):
    global blocked_queues
    if counter_name not in blocked_queues:
        return 0
    return blocked_queues[counter_name].qsize()


def get_bus_reinject_queue(host=None, port=None, unix_domain_socket=None):
    global bus_reinject_queues
    if unix_domain_socket is not None:
        key = unix_domain_socket
    else:
        key = "%s:%i" % (host, port)
    if key not in bus_reinject_queues:
        bus_reinject_queues[key] = toro.PriorityQueue()
    return bus_reinject_queues[key]


def get_redis_pool(host=None, port=None, unix_domain_socket=None):
    global redis_pools
    if unix_domain_socket is not None:
        key = unix_domain_socket
    else:
        key = "%s:%i" % (host, port)
    if key not in redis_pools:
        kwargs = {"connect_timeout": options.timeout,
                  "client_timeout": REDIS_POOL_CLIENT_TIMEOUT,
                  "aggressive_write": True}
        if unix_domain_socket is not None:
            kwargs["unix_domain_socket"] = unix_domain_socket
        else:
            kwargs["tcp_nodelay"] = True
            kwargs["host"] = host
            kwargs["port"] = port
        redis_pools[key] = tornadis.ClientPool(**kwargs)
    return redis_pools[key]


def get_redis_client(host=None, port=None, unix_domain_socket=None):
    kwargs = {"connect_timeout": options.timeout, "aggressive_write": True}
    if unix_domain_socket is not None:
        kwargs["unix_domain_socket"] = unix_domain_socket
    else:
        kwargs["tcp_nodelay"] = True
        kwargs["host"] = host
        kwargs["port"] = port
    return tornadis.Client(**kwargs)


def format_redis_server(host=None, port=None, unix_domain_socket=None,
                        queue=None, queues=None):
    qs = queues
    if queue is not None:
        h = queue.host
        p = queue.port
        uds = queue.unix_domain_socket
        if queues is not None:
            qs = queue.queues
    else:
        h = host
        p = port
        uds = unix_domain_socket
    if qs is not None:
        qs_string = "/" + ",".join(qs)
    else:
        qs_string = ""
    if uds is not None:
        return "redis://%s%s" % (uds, qs_string)
    else:
        return "redis://%s:%i%s" % (h, p, qs_string)


@tornado.gen.coroutine
def request_redis_handler(queue, single_iteration=False):
    global expired_request_counter
    redis = get_redis_client(queue.host, queue.port, queue.unix_domain_socket)
    brpop_args = queue.queues + [BRPOP_TIMEOUT]
    while stopping < 1:
        tmp = yield redis.call('BRPOP', *brpop_args)
        if isinstance(tmp, tornadis.ConnectionError):
            logger.warning("connection error while brpoping queues %s "
                           "=> sleeping 5s and retrying",
                           format_redis_server(queue=queue))
            yield tornado.gen.sleep(5)
            continue
        if tmp:
            redis_queue, request = tmp
            exchange = HTTPRequestExchange(request, queue, redis_queue)
            launch_exchange_or_queue_it(exchange)
        if single_iteration:
            break
    logger.info("request_redis_handler %s stopped",
                format_redis_server(queue=queue))


@tornado.gen.coroutine
def process_request(exchange, before):
    global running_exchanges, total_request_counter
    async_client = tornado.httpclient.AsyncHTTPClient()
    request = exchange.request
    request.connect_timeout = options.timeout
    request.request_timeout = options.timeout
    request.decompress_response = False
    request.follow_redirects = False
    response_key = exchange.extra_dict['response_key']
    queue = exchange.queue
    rid = exchange.request_id
    if options.add_thr_extra_headers:
        if queue.unix_domain_socket is not None:
            request.headers['X-Thr-Bus'] = queue.unix_domain_socket
        else:
            request.headers['X-Thr-Bus'] = "%s:%i" % (queue.host, queue.port)
    logger.debug("Calling %s on %s (#%s)....", request.method, request.url,
                 rid)
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
    td_ms = timedelta_total_ms(dt)
    logger.info("Got a reply #%i after %i ms (execution) and %i ms (queue) "
                "for (#%s, %s on %s)", response.code,
                td_ms, exchange.lifetime_in_local_queue_ms() - td_ms,
                rid, request.method, request.url)
    redis_pool = get_redis_pool(queue.host, queue.port,
                                queue.unix_domain_socket)
    pipeline = tornadis.Pipeline()
    pipeline.stack_call("LPUSH", response_key,
                        serialize_http_response(response))
    pipeline.stack_call("EXPIRE", response_key, options.timeout)
    with (yield redis_pool.connected_client()) as redis:
        redis_res = yield redis.call(pipeline)
        if redis_res is None or \
                isinstance(redis_res, tornadis.ConnectionError) or \
                len(redis_res) != 2 or \
                not isinstance(redis_res[0], six.integer_types) or \
                not isinstance(redis_res[1], six.integer_types):
            logger.warning("can't send the result on %s for "
                           "request #%s", format_redis_server(queue=queue),
                           rid)


def reinject_blocking_queue(counter):
    choosen_counter = counter + "___reinject"
    while True:
        try:
            tmp = blocked_queue_get_nowait(counter)
        except _queue.Empty:
            break
        ex = tmp[1]
        res = launch_exchange_or_queue_it(ex, choosen_counter=choosen_counter)
        if res is not None and res is not True:
            # The request is not accepted because some counters are full
            if counter in res:
                # The current counter is full => stopping the reinject process
                break
    # Let's reinject jobs into the blocking queue (from the temporary queue)
    while True:
        try:
            tmp = blocked_queue_get_nowait(choosen_counter)
        except _queue.Empty:
            break
        blocked_queue_put_nowait(counter, tmp[0], tmp[1])


def queue_for_bus_reinject(host, port, unix_domain_socket, priority, exchange,
                           remove_from_blocked_exchange=True):
    global blocked_exchanges
    get_bus_reinject_queue(host, port,
                           unix_domain_socket).put_nowait((priority, exchange))
    rid = exchange.request_id
    if remove_from_blocked_exchange:
        if rid in blocked_exchanges:
            del(blocked_exchanges[rid])


@tornado.gen.coroutine
def bus_reinject_handler(host=None, port=None, unix_domain_socket=None,
                         single_iteration=False):
    global bus_reinject_counter
    redis = get_redis_client(host=host, port=port,
                             unix_domain_socket=unix_domain_socket)
    queue = get_bus_reinject_queue(host, port, unix_domain_socket)
    deadline = timedelta(seconds=1)
    while True:
        if stopping >= 4 and queue.qsize() == 0:
            break
        try:
            priority, exchange = yield queue.get(deadline=deadline)
        except toro.Timeout:
            continue
        rid = exchange.request_id
        logger.debug("reinject request #%s on %s", rid,
                     format_redis_server(host, port, unix_domain_socket,
                                         queues=[exchange.redis_queue]))
        result = yield redis.call('LPUSH', exchange.redis_queue,
                                  exchange.serialized_request)
        if not isinstance(result, six.integer_types):
            redis_string = format_redis_server(host, port,
                                               unix_domain_socket,
                                               queues=[exchange.redis_queue])
            if stopping >= 4:
                logger.warning("can't reinject request #%s on "
                               "%s but we are stopping "
                               "=> loosing requests", rid, redis_string)
                break
            logger.warning("can't reinject request #%s on %s "
                           "=> sleeping 5s and re-queueing the request",
                           rid, redis_string)
            yield tornado.gen.sleep(5)
            queue.put_nowait((priority, exchange))
        else:
            bus_reinject_counter += 1
        if single_iteration:
            break
    logger.info("bus_reinject_handler %s stopped",
                format_redis_server(host, port, unix_domain_socket))


@tornado.gen.coroutine
def expiration_handler(single_iteration=False):
    global blocked_exchanges, expired_request_counter
    while stopping < 2:
        to_trash = []
        queues_to_find = set()
        for rid, tmp in blocked_exchanges.items():
            counter, exchange = tmp
            lifetime = exchange.lifetime()
            local_queue_ms = exchange.lifetime_in_local_queue_ms()
            if lifetime > options.max_lifetime:
                logger.warning("expired request #%s (lifetime: %i) blocked "
                               "=> trash it", rid, lifetime)
                expired_request_counter += 1
                to_trash.append(rid)
                queues_to_find.add(counter)
            elif local_queue_ms > options.max_local_queue_lifetime_ms:
                host = exchange.queue.host
                port = exchange.queue.port
                uds = exchange.queue.unix_domain_socket
                priority = exchange.priority
                logger.info("request #%s spent %s ms in local queue "
                            " => reuploading it on %s", rid,
                            local_queue_ms,
                            format_redis_server(host, port, uds))
                queue_for_bus_reinject(host, port, uds, priority, exchange,
                                       remove_from_blocked_exchange=False)
                to_trash.append(rid)
                queues_to_find.add(counter)
        for counter in queues_to_find:
            to_reinject = []
            while True:
                try:
                    tmp = blocked_queue_get_nowait(counter)
                except _queue.Empty:
                    break
                if tmp[1].request_id not in to_trash:
                    to_reinject.append(tmp)
            for tmp in to_reinject:
                blocked_queue_put_nowait(counter, tmp[0], tmp[1])
        for trashed_rid in to_trash:
            del(blocked_exchanges[trashed_rid])
        yield tornado.gen.sleep(0.1)
    logger.info("expiration_handler stopped")


def launch_exchange_or_queue_it(exchange, choosen_counter=None):
    global expired_request_counter, blocked_exchanges, running_exchanges
    rid = exchange.request_id
    lifetime = exchange.lifetime()
    priority = exchange.priority
    if lifetime > options.max_lifetime:
        logger.warning("expired request #%s (lifetime: %i) got from "
                       "local queue => trash it", rid, lifetime)
        expired_request_counter += 1
        if rid in blocked_exchanges:
            del(blocked_exchanges[rid])
        return None
    if stopping >= 2:
        host = exchange.queue.host
        port = exchange.queue.port
        uds = exchange.queue.unix_domain_socket
        queue_for_bus_reinject(host, port, uds, priority, exchange)
        if rid in blocked_exchanges:
            del(blocked_exchanges[rid])
        return None
    if exchange.conditions is None:
        exchange.conditions = Limits.conditions(exchange.request)
    accepted, counters = conditional_incr_counters(exchange.conditions)
    if accepted is False:
        if choosen_counter is None:
            choosen_counter = min(counters, key=get_blocked_queue_size)
        try:
            blocked_queue_put_nowait(choosen_counter, priority, exchange)
            logger.debug("request %s blocked by %s counter, queued in "
                         "blocking queue", rid, choosen_counter)
            if rid not in blocked_exchanges:
                blocked_exchanges[rid] = (choosen_counter, exchange)
        except _queue.Full:
            host = exchange.queue.host
            port = exchange.queue.port
            uds = exchange.queue.unix_domain_socket
            logger.debug("the blocking queue for counter %s is full => "
                         "re reuploading request %s on %s",
                         choosen_counter, rid,
                         format_redis_server(host, port, uds))
            queue_for_bus_reinject(host, port, uds, priority, exchange)
            if rid in blocked_exchanges:
                del(blocked_exchanges[rid])
        return counters
    else:
        if rid in blocked_exchanges:
            del(blocked_exchanges[rid])
        before = datetime.now()
        running_exchanges[rid] = (before, exchange)
        future = process_request(exchange, before)
        callback = functools.partial(process_request_callback, rid, counters)
        tornado.ioloop.IOLoop.instance().add_future(future, callback)
        return True


def process_request_callback(rid, counters, future):
    global running_exchanges, total_request_counter
    del(running_exchanges[rid])
    decr_counters(counters)
    total_request_counter += 1
    for counter in counters:
        reinject_blocking_queue(counter)
    exception = future.exception()
    if exception is not None:
        logging.exception(format_future_exception(future))


def write_stats():
    stats = {"epoch": time.time(), "stopping_mode": stopping}
    for key, queue in bus_reinject_queues.items():
        stats["bus_reinject_queue_%s_size" % key] = queue.qsize()
    running_requests = {}
    now = datetime.now()
    for key, tmp in running_exchanges.items():
        before, exchange = tmp
        big_priority = exchange.priority / 100000000000000
        running_requests[key] = {"method": exchange.request.method,
                                 "url": exchange.request.url,
                                 "since_ms": timedelta_total_ms(now - before),
                                 "big_priority": big_priority}
    stats["running_requests"] = running_requests
    stats["blocked_requests"] = len(blocked_exchanges)
    stats["running_bus_reinject_handler_number"] = \
        running_bus_reinject_handler_number
    stats["running_request_redis_handler_number"] = \
        running_request_redis_handler_number
    stats['bus_reinject_counter'] = bus_reinject_counter
    stats['total_request_counter'] = total_request_counter
    stats['expired_request_counter'] = expired_request_counter
    stats['counters'] = {}
    for name, limit in six.iteritems(Limits.limits):
        if limit.show_in_stats:
            stats['counters'][name + "_limit"] = limit.limit
            if limit.counter_suffix("foo") == "":
                stats['counters'][name + "_value"] = get_counter(name)
                stats['counters'][name + "_blocks"] = get_counter_blocks(name)
                stats['counters'][name + "_queue"] = \
                    get_blocked_queue_size(name)
            else:
                global_name = get_global_counter_name(name)
                stats['counters'][name + "_globalvalue"] = \
                    get_counter(global_name)
                stats['counters'][name + "_globalblocks"] = \
                    get_counter_blocks(global_name)

    with open(options.stats_file, "w") as f:
        f.write(json.dumps(stats, indent=4))


def stop_loop(future):
    exc = future.exception()
    if exc is not None:
        logging.exception(format_future_exception(future))
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
        elif stopping == 2:
            stopping += 1
            tornado.ioloop.IOLoop.instance().call_later(0.01, _stop_loop)
        elif stopping == 3:
            if len(running_exchanges) == 0:
                stopping += 1
            else:
                logger.info("waiting for %i request(s) to finish...",
                            len(running_exchanges))
                tornado.ioloop.IOLoop.instance().call_later(1, _stop_loop)
        elif stopping == 4:
            running_bus_reinject_handler_number -= 1
            if running_bus_reinject_handler_number == 0:
                stopping += 1
                logger.info("stopping ioloop...")
                tornado.ioloop.IOLoop.instance().stop()
        else:
            stopping += 1


def sig_handler(sig, frame):
    logging.info('caught signal: %s', sig)
    tornado.ioloop.IOLoop.instance().add_callback_from_signal(shutdown)


def shutdown():
    global stopping
    stopping = 1


def main():
    global running_request_redis_handler_number,\
        running_bus_reinject_handler_number
    parse_command_line()
    if options.config is not None:
        exec(open(options.config).read(), {})
    loop = tornado.ioloop.IOLoop.instance()
    loop.set_blocking_log_threshold(1)
    launched_bus_reinject_handlers = {}
    for queue in Queues:
        host = queue.host
        port = queue.port
        uds = queue.unix_domain_socket
        workers = queue.workers
        for i in range(0, workers):
            loop.add_future(request_redis_handler(queue), stop_loop)
            running_request_redis_handler_number += 1
        if "%s:%i" % (host, port) not in launched_bus_reinject_handlers:
            loop.add_future(bus_reinject_handler(host=host, port=port,
                                                 unix_domain_socket=uds),
                            stop_loop)
            launched_bus_reinject_handlers["%s:%i" % (host, port)] = True
            running_bus_reinject_handler_number += 1
    loop.add_future(expiration_handler(), stop_loop)
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
