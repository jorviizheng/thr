from thr.redis2http.queue import add_queue


# Pop requests from thr:queue:hello and forward them to our service
add_queue('thr:queue:hello', http_port=9999)
