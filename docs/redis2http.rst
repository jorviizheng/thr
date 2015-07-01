redis2http configuration
------------------------

redis2http is configured with a Python script calling essentially two functions:

    * :py:func:`~thr.redis2http.queue.add_queue`
    * :py:func:`~thr.redis2http.limits.add_max_limit`


Here is an example of configuration file for redis2http::


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


To use a configuration file, start ``redis2http`` with the ``--config`` argument::

    $ redis2http --config=redis2http_conf.py
    [I 150701 16:43:28 stack_context:275] redis2http started
