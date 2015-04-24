#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import re
from fnmatch import fnmatch
from tornado import gen
from tornado.escape import parse_qs_bytes
from tornado.httputil import HTTPHeaders


ruleset = []
regexp = re.compile
RegexpType = type(re.compile(''))


class glob(object):
    """
    Adapter providing a regexp-like interface for glob expressions

    Args:
        pattern: a glob pattern

    >>> glob_obj = glob("*.txt")
    >>> glob_obj.match("foo.txt")
    True
    >>> glob_obj.match("foo.py")
    False
    """

    def __init__(self, pattern):
        self.pattern = pattern

    def match(self, string):
        """
        Args:
            string: a string to match against the glob pattrn
        Return:
            bool
        """
        return fnmatch(string, self.pattern)


class Criteria(object):
    """
    A set of criteria which may be satisfied or not. Each criterion is
    supplied as a keyword argument when creating :class:`Criteria`
    instances and may be a string, a :class:`~thr.http2redis.rules.glob` object
    or a compiled regular expression object. A special criterion named
    `request` may be a callable or a coroutine.

    Keyword Args:
        path: check against the request path
        method: check the HTTP method
        remote_ip: check the remote IP address
        request: callback taking a request object as its sole argument
                 and returning a boolean value
    """

    def __init__(self, **kwargs):
        self.criteria = kwargs

    def check_request_attribute(self, request, name):
        criterion = self.criteria.get(name)
        if criterion is None:
            return True

        value = getattr(request, name)
        if isinstance(criterion, (glob, RegexpType)):
            return criterion.match(value)
        else:
            return value == criterion

    @gen.coroutine
    def match(self, request):
        """Check a request against the criteria

        Args:
            request: A Tornado HTTPServerRequest object

        Returns:
            bool
        """
        futures = [
            gen.maybe_future(self.check_request_attribute(request, attrname))
            for attrname in ('method', 'path', 'remote_ip')
        ]
        if 'request' in self.criteria:
            callback = self.criteria['request']
            future = gen.maybe_future(callback(request))
            futures.append(future)
        result = yield futures
        raise gen.Return(all(result))


class Actions(object):
    """
    A set of actions to perform on a request/response exchange.

    Each action is supplied as a keyword argument when instanciating
    :class:`Actions` and may be an action-specific value or a callable
    accepting an :class:`~thr.http2redis.HTTPExchange` as its sole argument and
    returning a value.

    Keyword Args:
        set_input_header: a pair of header name and value
        set_status_code: and HTTP response status code
        set_queue: the name of a Redis queue in which to push the request
    """

    def __init__(self, **kwargs):
        self.actions = kwargs
        self.action_names = [
            name for name in dir(self)
            if name.startswith('set_') or name.startswith('add_')
            or name.startswith('del_')
        ]

    def execute_output_actions(self, exchange):
        return self._execute(exchange, "output")

    def execute_input_actions(self, exchange):
        return self._execute(exchange, "input")

    @gen.coroutine
    def _execute(self, exchange, mode):
        """
        Apply actions to the HTTP exchange.

        Args:
            exchange: An :class:`~thr.http2redis.HTTPExchange` instance
            mode (string): input for executing input actions,
                output for executing output actions
        """
        if mode not in ("input", "output"):
            raise Exception("mode must be input or output")
        futures = {}
        for action_name in self.action_names:
            action = self.actions.get(action_name)
            if not action:
                continue
            if mode == "output" and "_output_" not in action_name:
                continue
            if action:
                if callable(action):
                    value = action(exchange.request)
                else:
                    value = action
                future = gen.maybe_future(value)
                futures[action_name] = future

        result_dict = yield futures

        for action_name in self.action_names:
            action = self.actions.get(action_name)
            if not action:
                continue
            if mode == "output" and "_output_" not in action_name:
                continue
            set_value = getattr(self, action_name)
            value = result_dict[action_name]
            set_value(exchange, value)

    def set_input_header(self, exchange, value):
        header_name, header_value = value
        exchange.request.headers[header_name] = header_value

    def add_input_header(self, exchange, value):
        header_name, header_value = value
        exchange.request.headers.add(header_name, header_value)

    def del_input_header(self, exchange, value):
        try:
            del(exchange.request.headers[value])
        except KeyError:
            pass

    def set_output_header(self, exchange, value):
        header_name, header_value = value
        headers = exchange.response.get('headers', HTTPHeaders())
        headers[header_name] = header_value

    def add_output_header(self, exchange, value):
        header_name, header_value = value
        headers = exchange.response.get('headers', HTTPHeaders())
        headers.add(header_name, header_value)

    def del_output_header(self, exchange, value):
        if 'headers' not in exchange.response:
            return
        try:
            del(exchange.response['headers'][value])
        except KeyError:
            pass

    def set_status_code(self, exchange, value):
        exchange.response['status_code'] = value

    def set_queue(self, exchange, value):
        exchange.queue = value

    def set_path(self, exchange, value):
        exchange.request.path = value

    def set_method(self, exchange, value):
        exchange.request.method = value

    def set_host(self, exchange, value):
        exchange.request.host = value

    def set_remote_ip(self, exchange, value):
        exchange.request.remote_ip = value

    def set_input_body(self, exchange, value):
        exchange.request.body = value

    def set_output_body(self, exchange, value):
        exchange.response['body'] = value

    def set_query_string(self, exchange, value):
        exchange.request.query_arguments = \
            parse_qs_bytes(value, keep_blank_values=True)

    def add_query_string_arg(self, exchange, value):
        arg_name, arg_value = value
        args = exchange.request.query_arguments
        if arg_name in args:
            args[arg_name].append(arg_value)
        else:
            args[arg_name] = [arg_value]

    def set_query_string_arg(self, exchange, value):
        arg_name, arg_value = value
        args = exchange.request.query_arguments
        args[arg_name] = [arg_value]

    def del_query_string_arg(self, exchange, value):
        try:
            del(exchange.request.query_arguments[value])
        except KeyError:
            pass


class Rule(object):

    def __init__(self, criteria, actions, **kwargs):
        self.criteria = criteria
        self.actions = actions
        self.stop = kwargs.get('stop', False)


class Rules(object):

    rules = []

    @classmethod
    def reset(cls):
        cls.rules = []

    @classmethod
    def add(cls, criteria, actions, **kwargs):
        cls.rules.append(Rule(criteria, actions, **kwargs))

    @classmethod
    def count(cls):
        return len(cls.rules)

    @classmethod
    def execute_input_actions(cls, exchange):
        return cls._execute(exchange, "input")

    @classmethod
    def execute_output_actions(cls, exchange):
        return cls._execute(exchange, "output")

    @classmethod
    @gen.coroutine
    def _execute(cls, exchange, mode):
        for rule in cls.rules:
            match = yield rule.criteria.match(exchange.request)
            if match:
                yield rule.actions._execute(exchange, mode)
                if rule.stop:
                    return


def add_rule(criteria, actions, **kwargs):
    """
    Add a rule that will execute :class:`Actions` based on :class:`Criteria`.

    Args:
        criteria: A :class:`Criteria` instance
        actions: An :class:`Actions` instance

    Keyword Args:
        stop: if True, don't execute subsequent rules if this one matches
        (default False)

    Returns:
        None
    """
    Rules.add(criteria, actions, **kwargs)
