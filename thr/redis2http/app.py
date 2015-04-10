#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from functools import partial
import tornado
import tornadis
import toro

from thr.http2redis.limits import
from thr.utils import unserialize_http_request, serialize_http_response



request_queue = toro.Queue()
redis_request_pool = tornadis.ClientPool()
redis_hash_pool = tornadis.ClientPool() #Probably not needed, a "standard" redis connection with a pipeline may be better


def get_busy_workers(hash):
    with (yield redis_hash_pool.connected_client()) as redis:
        return yield redis.call('GET', hash)


@tornado.gen.coroutine
def request_redis_handler():
    # Needs to be rewritten : there is several redis keys to check, and it must be done in an intelligent way (i.e. depending on how many workers are currently free, etc)
    with (yield redis_request_pool.connected_client()) as redis:
        request = yield redis.call('BRPOP', 'to_be_clarified', 5)
        if request:
            yield request_queue.put(request)


@tornado.gen.coroutune
def finalize_request(response_key, hashes, response):
    """
    Callback to upload the http response on redis, and update the workers counters for each hash
    """
    with (yield redis_request_pool.connected_client()) as redis:
        yield redis.call('LPUSH', response_key, serialize_http_response(response))
    for hash in hashes:
        with (yield redis_hash_pool.connected_client()) as redis:
            yield redis.call('DECR', hash)


@tornado.gen.coroutine
def process_request(request):
    """
    Update the workers counters for each hash and send the request to a worker
    """
    with (yield redis_hash_pool.connected_client()) as redis:
        for hash in hashes:
            yield redis.call('INCR', hashes)
    async_client = tornado.httpclient.AsynHTTPClient()
    return yield async_client.fetch(request)


@tornado.gen.coroutine
def request_toro_handler():
    """
    Get a request for the toro queue, check the limits for each hash, and process the request if there is a free worker
    """
    serialized_request = yield request_queue.get()
    # we can avoid premature deserialization if the hash functions take the serialized request as parameter ?
    request, body_link, http_dict, extra_dict = unserialize_http_request(serialized_request, force_host="localhost:8082") #force_host to be fixed
    # Need to get the body if body_link is provided

    # hashes get calculated twice, this is bad...
    hashes = []
    for limits in Hashes.hashes:
        hash = limits.get_hash(request)
        hashes.append(hash)
        if not limits.check(request, get_busy_worker(hash)):
            # reupload the request to the bus ?
            with (yield redis_request_pool.connected_client()) as redis:
                # We still have the serialized request, might as well reuse it
                yield redis.call('LPUSH', 'to_be_clarified (cf request_redis_handler)', serialized_request)
    else:
        IOLoop.instance().add_future(process_request(request), partial(finalize_request, extra_dict["response_key"], Hashes.get_hashes(request)))

