#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from thr.utils import unserialize_request_message, make_unique_id
import time


class HTTPRequestExchange(object):

    def __init__(self, request, queue, redis_queue=None):
        self.serialized_request = request
        self.queue = queue
        if redis_queue is None:
            self.redis_queue = queue.queues[0]
        else:
            self.redis_queue = redis_queue
        self.local_queue_time = time.time()
        self.conditions = None
        self.__request = None
        self.__body_link = None
        self.__extra_dict = None
        self.__request_id = None
        self.__priority = None
        self.creation_time = time.time()

    def unserialize_request(self):
        force_host = "%s:%i" % (self.queue.http_host, self.queue.http_port)
        self.__request, self.__body_link, self.__extra_dict = \
            unserialize_request_message(self.serialized_request,
                                        force_host=force_host)

    @property
    def request(self):
        if not self.__request:
            self.unserialize_request()
        return self.__request

    @property
    def body_link(self):
        if not self.__request:
            self.unserialize_request()
        return self.__body_link

    @property
    def extra_dict(self):
        if not self.__request:
            self.unserialize_request()
        return self.__extra_dict

    @property
    def priority(self):
        if not self.__priority:
            if not self.__request:
                self.unserialize_request()
            big = self.__extra_dict.get('priority', 5)
            little = int(self.creation_time * 1000)
            self.__priority = big * 10000000000000 + little
        return self.__priority

    @property
    def request_id(self):
        if not self.__request_id:
            self.unserialize_request()
            self.__request_id = self.__extra_dict.get('request_id',
                                                      make_unique_id())
        return self.__request_id

    def lifetime_in_local_queue_ms(self):
        return int((time.time() - self.local_queue_time) * 1000)

    def lifetime(self):
        if not self.__request:
            self.unserialize_request()
        now = time.time()
        dt = now - self.__extra_dict.get('creation_time', now)
        # creation_time can be set by another not time synchronized box
        dt = max(0, dt)
        return int(dt)
