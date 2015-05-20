#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from thr import DEFAULT_HTTP_PORT


# Trick to be able to iter over Queues
class MetaQueues(type):
    def __iter__(self):
        return self.iterqueues()


class Queues(object):

    __metaclass__ = MetaQueues
    queues = []

    @classmethod
    def reset(cls):
        cls.queues = []

    @classmethod
    def add(cls, queue):
        cls.queues.append(queue)

    @classmethod
    def iterqueues(cls):
        return iter(cls.queues)


class Queue(object):

    def __init__(self, host, port, queue, http_host="localhost",
                 http_port=DEFAULT_HTTP_PORT, workers=1):
        self.host = host
        self.port = port
        self.queue = queue
        self.http_host = http_host
        self.http_port = http_port
        self.workers = workers


def add_queue(host, port, queue, http_host="localhost",
              http_port=DEFAULT_HTTP_PORT, workers=1):
    Queues.add(Queue(host, port, queue, http_host, http_port, workers))
