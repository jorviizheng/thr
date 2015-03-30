#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

import re
from fnmatch import fnmatch
from tornado import gen


ruleset = []
regexp = re.compile
RegexpType = type(re.compile(''))


class glob(object):
    """Adapter providing a regexp-like interface for glob expressions"""
    def __init__(self, pattern):
        """
        Constructor

        Args:
            pattern: a glob patter
        """
        self.pattern = pattern

    def match(self, string):
        return fnmatch(string, self.pattern)


class Criteria(object):
    """Encapsulate a series of criteria which may be satisfied or not."""

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
            boolean
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

    def __init__(self, **kwargs):
        self.actions = kwargs
        self.action_names = [
            name for name in dir(self)
            if name.startswith('set_')
        ]

    @gen.coroutine
    def execute(self, exchange):
        futures = {}
        for action_name in self.action_names:
            action = self.actions.get(action_name)
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
            if action:
                set_value = getattr(self, action_name)
                value = result_dict[action_name]
                set_value(exchange, value)

    def set_input_header(self, exchange, value):
        header_name, header_value = value
        exchange.request.headers[header_name] = header_value

    def set_status_code(self, exchange, value):
        exchange.response['status_code'] = value

    def set_queue(self, exchange, value):
        exchange.queue = value


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
    @gen.coroutine
    def execute(cls, exchange):
        for rule in cls.rules:
            match = yield rule.criteria.match(exchange.request)
            if match:
                yield rule.actions.execute(exchange)
                if rule.stop:
                    return


def add_rule(criteria, actions, **kwargs):
    Rules.add(criteria, actions, **kwargs)
