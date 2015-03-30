from thr.http2redis.rules import add_rule, Criteria, Actions


add_rule(Criteria(path='/foo'), Actions(set_status_code=201))
add_rule(Criteria(path='/bar'), Actions(set_status_code=202))
