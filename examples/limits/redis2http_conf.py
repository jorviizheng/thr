from thr.redis2http.queue import add_queue
from thr.redis2http.limits import add_max_limit


# Pop requests from thr:queue:hello and forward them to our service
add_queue('thr:queue:hello', http_port=9999)


def limit_foo(request):
    return request.headers.get('Foo') or 'none'

# Limit requests based on a header
add_max_limit('limit_foo_header', limit_foo, "bar", 2)
