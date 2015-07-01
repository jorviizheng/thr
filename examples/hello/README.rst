Start the app server::

    $ python app_server.py 
    Serving app on http://localhost:9999


Start http2redis::

    $ http2redis --config=http2redis_conf.py 
    Start http2redis on http://localhost:8888

Start redis2http::

    $ redis2http --config=redis2http_conf.py
    [I 150701 10:18:06 stack_context:275] redis2http started


Make an HTTP request::

    $ curl http://localhost:8888
    Hello World
