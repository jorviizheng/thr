#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from functools import partial
import tornado
from tornado.options import define, options, parse_command_line
import tornadis
import toro

from thr.redis2http.limits import Limits
from thr.redis2http.exchange import Queues, HTTPRequestExchange
from thr.utils import serialize_http_response
from thr import DEFAULT_TIMEOUT


define("redis2http_config", help="Path to config file")
define("redis2http_timeout", type=int, help="Timeout in second for a request",
       default=DEFAULT_TIMEOUT)


request_queue = toro.Queue()
redis_pools = {}
redis_hash_pool = tornadis.ClientPool()

async_client_impl = "tornado.simple_httpclient.SimpleAsyncHTTPClient"
tornado.httpclient.AsyncHTTPClient.configure(async_client_impl,
                                             max_clients=100000)


def get_redis_pool(host, port):
    global redis_pools
    key = "%s:%i" % (host, port)
    if key not in redis_pools:
        redis_pools[key] = \
            tornadis.ClientPool(host=host, port=port,
                                connect_timeout=options.redis2http_timeout)
    return redis_pools[key]


@tornado.gen.coroutine
def get_busy_workers(hash):
    with (yield redis_hash_pool.connected_client()) as redis:
        nb_workers = yield redis.call('GET', hash)
    raise tornado.gen.Return(int(nb_workers))


@tornado.gen.coroutine
def request_redis_handler(queue, single_iteration=False):
    # Needs to be rewritten : there is several redis keys to check,
    # and it must be done in an intelligent way
    # (i.e. depending on how many workers are currently free, etc)
    loop = True
    while loop:
        if single_iteration:
            loop = False
        redis_request_pool = get_redis_pool(queue.host, queue.port)
        with (yield redis_request_pool.connected_client()) as redis:
            _, request = yield redis.call('BRPOP', queue.queue, 0)
            if request:
                yield request_queue.put(HTTPRequestExchange(request, queue))


@tornado.gen.coroutine
def finalize_request(queue, response_key, hashes, response):
    """
    Callback to upload the http response on redis,
    and update the workers counters for each hash
    """
    if hashes:
        pipeline = tornadis.Pipeline()
        for hash in hashes:
            pipeline.stack_call('DECR', hash)
        with (yield redis_hash_pool.connected_client()) as redis:
            yield redis.call(pipeline)
    redis_request_pool = get_redis_pool(queue.host, queue.port)
    with (yield redis_request_pool.connected_client()) as redis:
        yield redis.call('LPUSH', response_key,
                         serialize_http_response(response.result()))


@tornado.gen.coroutine
def process_request(request, hashes, body_link=None):
    """
    Update the workers counters for each hash and send the request to a worker
    """
    async_client = tornado.httpclient.AsyncHTTPClient()
    if body_link:
        body = async_client.fetch(body_link)
        # TODO : body uploaded on redis ?
    if hashes:
        pipeline = tornadis.Pipeline()
        for hash in hashes:
            pipeline.stack_call('INCR', hash)
        with (yield redis_hash_pool.connected_client()) as redis:
            yield redis.call(pipeline)
    if body_link:
        request.body = yield body
    response = yield async_client.fetch(request, raise_error=False)
    raise tornado.gen.Return(response)


@tornado.gen.coroutine
def request_toro_handler(single_iteration=False):
    """
    Get a request for the toro queue, check the limits for each hash,
    and process the request if there is a free worker
    """
    loop = True
    while loop:
        if single_iteration:
            loop = False
        exchange = yield request_queue.get()

        hashes = yield Limits.check(exchange.request)
        if hashes is None:
            # reupload the request to the bus
            redis_request_pool = get_redis_pool(exchange.queue.host,
                                                exchange.queue.port)
            with (yield redis_request_pool.connected_client()) as redis:
                # We still have the serialized request, might as well reuse it
                yield redis.call('LPUSH', exchange.queue.queue,
                                 exchange.serialized_request)
        else:
            tornado.ioloop.IOLoop.instance().add_future(
                process_request(exchange.request, hashes, exchange.body_link),
                partial(finalize_request, exchange.queue,
                        exchange.extra_dict["response_key"], hashes))


def stop_loop(future):
    exc = future.exception()
    if exc is not None:
        raise exc
    tornado.ioloop.IOLoop.instance().stop()


if __name__ == "__main__":
    parse_command_line()
    if options.redis2http_config is not None:
        exec(open(options.redis2http_config).read(), {})
    loop = tornado.ioloop.IOLoop.instance()
    for queue in Queues:
        loop.add_future(request_redis_handler(queue), stop_loop)
    loop.add_future(request_toro_handler(), stop_loop)
    loop.start()
