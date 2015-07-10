from thr.redis2http.limits import add_max_limit
from thr.redis2http.queue import add_queue


def priority_hash(request):
    priority = int(request.headers.get("X-MyApp-Priority", "5"))
    return "low" if priority > 6 else "high"

# Pop requests from a Redis queue named thr:queue:hello and forward them to port 9999
add_queue('thr:queue:hello', http_port=9999)

# Limit rate of requests with an X-MyApp-Priority header greater than 6
add_max_limit("low_priority", hash_func=priority_hash,
              hash_value="low", max_limit=50)
