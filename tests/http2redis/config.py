from tornado import gen
from thr.http2redis.rules import add_rule, Criteria, Actions


@gen.coroutine
def coroutine_set_status_code(exchange):
    yield gen.sleep(0.1)
    exchange.set_status_code(201)


add_rule(Criteria(path='/foo'),
         Actions(custom_input=coroutine_set_status_code))
add_rule(Criteria(path='/bar'), Actions(set_status_code=202))
