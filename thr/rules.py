import operator
import re
from fnmatch import fnmatch


def matchfn(pattern, string):
    "Wrapper qui intervertit les arguments de fnmatch"
    return fnmatch(string, pattern)


class Criteria(object):

    def __init__(self, **kwargs):
        self.criteria = kwargs

    def check_request_attribute(self, request, name, callback):
        value = getattr(request, name)
        criterion = self.criteria.get(name)
        if callable(criterion):
            if not criterion(value):
                return False
        elif criterion and not callback(criterion, value):
            return False
        return True

    def matches(self, request):
        if not self.check_request_attribute(request, 'method', operator.eq):
            return False

        if not self.check_request_attribute(request, 'path', re.search):
            return False

        if not self.check_request_attribute(request, 'remote_ip', matchfn):
            return False

        return True
