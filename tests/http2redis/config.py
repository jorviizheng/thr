from tornado import gen
from thr.http2redis.rules import add_rule, Criteria, Actions


@gen.coroutine
def set_status_code(request):
    raise gen.Return(201)


add_rule(Criteria(path='/foo'), Actions(set_status_code=set_status_code))
add_rule(Criteria(path='/bar'), Actions(set_status_code=202))
