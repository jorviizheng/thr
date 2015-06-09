#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from tornado.httputil import HTTPHeaders
from tornado.escape import parse_qs_bytes
from thr import DEFAULT_REDIS_HOST, DEFAULT_REDIS_PORT, DEFAULT_REDIS_QUEUE
from thr.utils import make_unique_id


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
        redis_host: the hostname or ip of the redis server where to
            push the request.
        redis_port: the port of the redis server where to push the request.
        redis_uds: path of a unix domain socket to connect to (if set,
            overrides, redis_host/redis_port attributes).
        redis_queue: the name of the redis queue where to push the request.
        keyvalues: a dict key=>value to store custom key/values (helper for
            config file).
        request_id: a unique id for the request
        priority: a value between 1 (high) and 99 (low) which will be the
            queue priority at redis2http side.
    """

    def __init__(self, request, default_redis_host=DEFAULT_REDIS_HOST,
                 default_redis_port=DEFAULT_REDIS_PORT,
                 default_redis_queue=DEFAULT_REDIS_QUEUE,
                 default_redis_uds=None):
        self.request = request
        self.response = HTTPExchangeResponse()
        self.redis_host = default_redis_host
        self.redis_port = default_redis_port
        self.redis_uds = default_redis_uds
        self.redis_queue = default_redis_queue
        self.keyvalues = {}
        self.output_default_body = None
        self.request_id = make_unique_id()
        self.priority = 50
        self.matched_rules = None

    def set_custom_value(self, key, value):
        self.keyvalues[key] = value

    def get_custom_value(self, key, default=None):
        return self.keyvalues.get(key, default)

    def del_custom_value(self, key):
        if key in self.keyvalues:
            del(self.keyvalues[key])

    def set_input_header(self, value):
        header_name, header_value = value
        self.request.headers[header_name] = header_value

    def set_input_priority(self, value):
        priority = int(value)
        self.priority = min(99, max(1, priority))

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

    def set_redis_queue(self, value):
        self.redis_queue = value

    def set_redis_host(self, value):
        self.redis_host = value

    def set_redis_uds(self, value):
        self.redis_uds = value

    def set_redis_port(self, value):
        self.redis_port = value

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

    def set_output_default_body(self, value):
        self.output_default_body = value

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

    def get_method(self):
        return self.request.method

    def get_path(self):
        return self.request.path

    def get_remote_ip(self):
        return self.request.remote_ip
