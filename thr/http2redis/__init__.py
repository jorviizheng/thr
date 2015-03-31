#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.


class HTTPExchange(object):
    """
    Encapsulate an HTTP request/response exchange.

    Attributes:
        request: A Tornado HTTPServerRequest object
        response: a dict holding attributes that will be set on the response
        queue: the name of the Redis queue where to push the request
    """

    def __init__(self, request):
        self.request = request
        self.response = {}
        self.queue = None
