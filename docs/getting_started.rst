Getting started
---------------

Hello THR
^^^^^^^^^

THR is made of two programs:

    * ``http2redis`` takes incoming requests and performs actions on those requests according to rules. One of the most common actions consists in inserting requests into Redis queues that will get consumed by ``redis2http``. When writing a request to a queue, ``http2redis`` specifies on which Redis key it wishes to receive the response and waits for a response on that key.
    * ``redis2http`` reads requests from incoming Redis queues, calls the actual underlying web services and writes responses back to the requested Redis key.

To get started, let's create a minimal web service that responds "Hello World" to any request:

.. literalinclude:: ../examples/hello/app_server.py

Let's create a minimal configuration file for http2redis:


.. literalinclude:: ../examples/hello/http2redis_conf.py

And here is a minimal configuration file for redis2http:

.. literalinclude:: ../examples/hello/redis2http_conf.py

.. include:: ../examples/hello/README.rst

The source code for this example can be found in directory ``examples/hello``.

Setting up limits
^^^^^^^^^^^^^^^^^

Now we're going to see how to set up limits based on characateristics of
incoming requests. In order to test this we need a web service that can
serve several simultaneous requests:


.. literalinclude:: ../examples/limits/app_server.py


We start this app using [Gunicorn](http://gunicorn.org/)::

    $ gunicorn -w 10 app_server:application
    [2015-07-10 17:17:28 +0000] [13971] [INFO] Starting gunicorn 19.2.1
    [2015-07-10 17:17:28 +0000] [13971] [INFO] Listening at: http://127.0.0.1:8000 (13971)
    [2015-07-10 17:17:28 +0000] [13971] [INFO] Using worker: sync
    [2015-07-10 17:17:28 +0000] [13976] [INFO] Booting worker with pid: 13976
    [...]

Now we add a limit to ``redis2http`` configuration file:

.. literalinclude:: ../examples/limits/redis2http_conf.py

This says that we won't allow more that two simultaneous requests that
have the HTTP header ``Foo`` with a value of ``bar``.

After restarting ``redis2http`` with the new configuration, let's see
how the limit affects performance. First, let's try ten concurrent
requests that shouldn't be affected by the limit::

    $ ab -c10 -n10 -H "Foo: baz" http://127.0.0.1:8888/|grep 'Time taken'
    Time taken for tests:   1.045 seconds

Each request takes one second to be served, but since we are able to serve all requests at the same time, it still takes
one second overall to serve ten requests. Now let's see what happens with requests that do match the limit criteria::

    $ ab -c10 -n10 -H "Foo: bar" http://127.0.0.1:8888/|grep 'Time taken'
    Time taken for tests:   5.055 seconds

Our limit of two simultaneous requests being now applied, it takes five
seconds to serve ten requests.

If you pass the same hash function ``hash_func`` as the ``hash_value``
argument (ie. repeating the ``hash_func`` argument twice), then the
limit will be applied on requests that have the same value for that hash
function. It can be useful to limit requests per user, for instance.
