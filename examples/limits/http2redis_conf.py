from thr.http2redis.rules import add_rule, Criteria, Actions


# Match any incoming request and push it to thr:queue:hello
add_rule(Criteria(), Actions(set_redis_queue='thr:queue:hello'))
