#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from tornado.httputil import HTTPHeaders
from tornado.escape import parse_qs_bytes


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

    def set_input_header(self, value):
        header_name, header_value = value
        self.request.headers[header_name] = header_value

    def add_input_header(self, value):
        header_name, header_value = value
        self.request.headers.add(header_name, header_value)

    def del_input_header(self, value):
        try:
            del(self.request.headers[value])
        except KeyError:
            pass

    def set_output_header(self, value):
        header_name, header_value = value
        self.response.headers[header_name] = header_value

    def add_output_header(self, value):
        header_name, header_value = value
        self.response.headers.add(header_name, header_value)

    def del_output_header(self, value):
        try:
            del(self.response.headers[value])
        except KeyError:
            pass

    def set_status_code(self, value):
        self.response.status_code = value

    def set_queue(self, value):
        self.queue = value

    def set_path(self, value):
        self.request.path = value

    def set_method(self, value):
        self.request.method = value

    def set_host(self, value):
        self.request.host = value

    def set_remote_ip(self, value):
        self.request.remote_ip = value

    def set_input_body(self, value):
        self.request.body = value

    def set_output_body(self, value):
        self.response.body = value

    def set_query_string(self, value):
        self.request.query_arguments = \
            parse_qs_bytes(value, keep_blank_values=True)

    def add_query_string_arg(self, value):
        arg_name, arg_value = value
        args = self.request.query_arguments
        if arg_name in args:
            args[arg_name].append(arg_value)
        else:
            args[arg_name] = [arg_value]

    def set_query_string_arg(self, value):
        arg_name, arg_value = value
        args = self.request.query_arguments
        args[arg_name] = [arg_value]

    def del_query_string_arg(self, value):
        try:
            del(self.request.query_arguments[value])
        except KeyError:
            pass
