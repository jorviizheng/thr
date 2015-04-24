#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from tornado.httputil import HTTPHeaders


class HTTPExchangeResponse(object):

    def __init__(self, status_code=None, body=None, headers=None):
        self.status_code = status_code
        self.body = body
        if headers:
            self.headers = headers
        else:
            self.headers = HTTPHeaders()


class HTTPExchange(object):
    """
    Encapsulate an HTTP request/response exchange.

    Attributes:
        request: A Tornado HTTPServerRequest object.
        response: a HTTPExchangeResponse object.
        queue: the name of the Redis queue where to push the request.
    """

    def __init__(self, request):
        self.request = request
        self.response = HTTPExchangeResponse()
        self.queue = None
