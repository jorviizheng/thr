Start the app server::

    $ gunicorn --workers 10 --bind 0.0.0.0:9999 app_server:application
    [...]
    [2015-07-20 09:05:36 +0000] [24161] [INFO] Listening at: http://0.0.0.0:9999 (24161)
    [...]


Start http2redis::

    $ http2redis --config=http2redis_conf.py 
    Start http2redis on http://localhost:8888

Start redis2http::

    $ redis2http --config=redis2http_conf.py
    [I 150701 10:18:06 stack_context:275] redis2http started


Make an HTTP request::

    $ curl http://localhost:8888
    Hello World
