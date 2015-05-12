#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.


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

    def __init__(self, host, port, queue):
        self.host = host
        self.port = port
        self.queue = queue


def add_queue(host, port, queue):
    Queues.add(Queue(host, port, queue))
