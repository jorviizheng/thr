#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import six

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

    def __init__(self, host, port, queues, http_host="localhost",
                 http_port=DEFAULT_HTTP_PORT, workers=1):
        self.host = host
        self.port = port
        self.queues = queues
        self.http_host = http_host
        self.http_port = http_port
        self.workers = workers


def add_queue(host, port, queues, http_host="localhost",
              http_port=DEFAULT_HTTP_PORT, workers=1):
    if isinstance(queues, six.string_types):
        Queues.add(Queue(host, port, [queues], http_host, http_port, workers))
    else:
        Queues.add(Queue(host, port, queues, http_host, http_port, workers))
