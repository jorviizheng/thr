#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import six

from thr import DEFAULT_HTTP_PORT
from thr.utils import UnixResolver


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

    def __init__(self, queues, host="localhost", port=6379,
                 http_host="localhost",
                 http_port=DEFAULT_HTTP_PORT, workers=1,
                 unix_domain_socket=None):
        self.host = host
        self.port = port
        self.unix_domain_socket = unix_domain_socket
        self.queues = queues
        self.http_host = http_host
        self.http_port = http_port
        self.workers = workers


def add_queue(queues, host="localhost", port=6379, http_host="localhost",
              http_port=DEFAULT_HTTP_PORT, workers=1,
              unix_domain_socket=None):
    if http_host.startswith('/'):
        # This is an unix socket
        new_http_host = UnixResolver.register_unixsocket(http_host)
    else:
        new_http_host = http_host
    if isinstance(queues, six.string_types):
        Queues.add(Queue([queues], host=host, port=port,
                         http_host=new_http_host,
                         http_port=http_port, workers=workers,
                         unix_domain_socket=unix_domain_socket))
    else:
        Queues.add(Queue(queues, host=host, port=port, http_host=new_http_host,
                         http_port=http_port, workers=workers,
                         unix_domain_socket=unix_domain_socket))
