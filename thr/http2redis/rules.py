import re
from fnmatch import fnmatch


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
        elif callable(criterion):
            return criterion(value)
        else:
            return value == criterion

    def match(self, request):
        """Check a request against creteria

        Args:
            request: A Tornado HTTPServerRequest object

        Returns:
            boolean
        """
        return all(
            self.check_request_attribute(request, attrname)
            for attrname in ('method', 'path', 'remote_ip')
        )


class Actions(object):

    def __init__(self, **kwargs):
        self.actions = kwargs

    def execute(self, exchange):
        set_input_header = self.actions.get('set_input_header')
        if set_input_header:
            exchange.request.headers[set_input_header[0]] = set_input_header[1]
        set_status_code = self.actions.get('set_status_code')
        if set_status_code:
            exchange.response['status_code'] = set_status_code


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
    def execute(cls, exchange):
        for rule in cls.rules:
            if rule.criteria.match(exchange.request):
                if rule.stop:
                    break
                rule.actions.execute(exchange)


def add_rule(criteria, actions, **kwargs):
    Rules.add(criteria, actions, **kwargs)
