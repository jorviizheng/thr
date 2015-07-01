#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from tornado import gen
from tornado import concurrent
from thr.http2redis.exchange import HTTPExchange
from thr.utils import glob, regexp


ruleset = []


class Criteria(object):
    """
    A set of criteria which may be satisfied or not. Each criterion is
    supplied as a keyword argument when creating :class:`Criteria`
    instances and may be a string, a :class:`~thr.http2redis.rules.glob` object
    or a compiled regular expression object. A special criterion named
    `custom` may be a callable or a coroutine.

    Keyword Args:
        path: check against the request path
        method: check the HTTP method
        remote_ip: check the remote IP address
        custom: callback taking a request object as its sole argument
                and returning a boolean value
    """

    def __init__(self, **kwargs):
        self.criterion_names = [
            name.replace('get_', '', 1) for name in dir(HTTPExchange)
            if name.startswith('get_') and not name.startswith('get_custom_')
        ]
        self.criteria = {x: y for x, y in kwargs.items()
                         if x in self.criterion_names or x == 'custom'}

    def eval_single_criterion_value(self, criterion, value):
        if isinstance(criterion, (glob, regexp)):
            return criterion.match(value)
        else:
            return value == criterion

    def check_exchange_attribute(self, exchange, name, criterion):
        getter = getattr(exchange, "get_%s" % name)
        value = getter()
        if isinstance(criterion, (list, tuple)):
            return any([self.eval_single_criterion_value(x, value)
                        for x in criterion])
        else:
            return self.eval_single_criterion_value(criterion, value)

    def match(self, exchange):
        """Check a request against the criteria

        Args:
            exchange: A HTTPExchange object

        Returns:
            bool
        """
        for name, criterion in self.criteria.items():
            if name != 'custom':
                tmp = self.check_exchange_attribute(exchange, name, criterion)
                if tmp is False:
                    return False
            else:
                callback = self.criteria['custom']
                if not callable(callback):
                    raise Exception("custom criteria must be callable")
                tmp = callback(exchange)
                if tmp is False:
                    return False
        return True


class Actions(object):
    """
    A set of actions to perform on a request/response exchange.

    Each action is supplied as a keyword argument when instanciating
    :class:`Actions` and may be an action-specific value or a callable
    accepting an :class:`~thr.http2redis.exchange.HTTPExchange` as its sole
    argument and returning a value.

    Keyword Args:
        set_input_header: a pair of header name and value
        set_status_code: and HTTP response status code
        set_redis_queue: the name of a Redis queue in which to push the request
        [...]
    """

    def __init__(self, **kwargs):
        self.action_names = [
            name for name in dir(HTTPExchange)
            if name.startswith('set_') or
            name.startswith('add_') or
            name.startswith('del_')
        ]
        self.input_actions = {x: y for x, y in kwargs.items()
                              if x in self.action_names and
                              (not self.is_output_action_name(x))}
        self.output_actions = {x: y for x, y in kwargs.items()
                               if x in self.action_names and
                               self.is_output_action_name(x)}
        self.action_names.append("custom_input")
        self.action_names.append("custom_output")
        self.custom_input_action = kwargs.get('custom_input', None)
        self.custom_output_action = kwargs.get('custom_output', None)

    def execute_output_actions(self, exchange):
        return self._execute(exchange, "output")

    def execute_input_actions(self, exchange):
        return self._execute(exchange, "input")

    def is_output_action_name(self, action_name):
        return action_name.endswith('_output') or '_output_' in action_name

    @gen.coroutine
    def _execute(self, exchange, mode):
        """
        Apply actions to the HTTP exchange.

        Args:
            exchange: An :class:`~thr.http2redis.exchange.HTTPExchange`
                instance
            mode (string): input for executing input actions,
                output for executing output actions
        """
        if mode not in ("input", "output"):
            raise Exception("mode must be input or output")
        if mode == 'output':
            actions = self.output_actions
            custom_action = self.custom_output_action
        else:
            actions = self.input_actions
            custom_action = self.custom_input_action
        for action_name, action in actions.items():
            if action:
                if callable(action):
                    value = action(exchange)
                    value_to_set = value
                else:
                    value_to_set = action
                if value_to_set is not None:
                    set_value = getattr(exchange, action_name)
                    set_value(value_to_set)
        if custom_action is not None:
            if callable(custom_action):
                value = custom_action(exchange)
                if isinstance(value, concurrent.Future):
                    if not value.done():
                        yield value
            else:
                raise Exception("custom_ actions must be callable")


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
        matched_rules = []
        test = True
        if exchange.matched_rules is not None:
            rules = exchange.matched_rules
            test = False
        else:
            rules = cls.rules
        for rule in rules:
            if test:
                match = rule.criteria.match(exchange)
            else:
                match = True
            if match:
                yield rule.actions._execute(exchange, mode)
                matched_rules.append(rule)
                if rule.stop:
                    break
        exchange.matched_rules = matched_rules


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
