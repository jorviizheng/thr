Getting started
---------------

Hello THR
^^^^^^^^^

THR is made of two programs:

    * ``http2redis`` takes incoming requests and performs actions on those requests according to rules. One of the most common actions consists in inserting requests into Redis queues that will get consumed by ``redis2http``. When appending a request to a queue, ``http2redis`` specifies on which Redis key it expects to receive the response and waits for a response on that key.
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

One of the interesting things about THR is the ability to do rate-limiting
based on various criteria.

Fixed limit values
''''''''''''''''''

In order to demonstrate how THR can do rate-limiting, we musn't be limited by
the backend ability to server multiple simultaneous requests. The basic
single-threaded "Hello World" example from the previous section won't be
suitable, so we prepare a minimal app that can be served with `Gunicorn
<http://gunicorn.org/>`_:


.. literalinclude:: ../examples/limits/app_server.py


We start this app with ten workers processes using Gunicorn::

    $ gunicorn --workers 10 --bind 0.0.0.0:9999 app_server:application
    [2015-07-10 17:17:28 +0000] [13971] [INFO] Starting gunicorn 19.2.1
    [2015-07-10 17:17:28 +0000] [13971] [INFO] Listening at: http://127.0.0.1:8000 (13971)
    [2015-07-10 17:17:28 +0000] [13971] [INFO] Using worker: sync
    [2015-07-10 17:17:28 +0000] [13976] [INFO] Booting worker with pid: 13976
    [...]

Now we add a limit to ``redis2http`` configuration file using the :py:func:`~thr.redis2http.limits.add_max_limit` function:

.. literalinclude:: ../examples/limits/redis2http_conf.py

This says that we won't allow more that two simultaneous requests that
have the HTTP header ``Foo`` with a value of ``bar``.

After restarting ``redis2http`` with the new configuration, let's see
how the limit affects performance. First, let's try ten concurrent
requests that don't match the criteria and therefore shouldn't be affected by the limit. We use the `Apache benchmarking tool <https://httpd.apache.org/docs/2.2/programs/ab.html>`_ to do that::

    $ ab -c10 -n10 -H "Foo: baz" http://127.0.0.1:8888/|grep 'Time taken'
    Time taken for tests:   1.045 seconds

Each request takes one second to be served, but since we are able to serve all requests at the same time, it still takes
one second overall to serve ten requests. Now let's see what happens with requests that do match the limit criteria::

    $ ab -c10 -n10 -H "Foo: bar" http://127.0.0.1:8888/|grep 'Time taken'
    Time taken for tests:   5.055 seconds

Our limit of two simultaneous requests being now applied, it takes five
seconds to serve ten requests.

Dynamic limit values
''''''''''''''''''''

If instead of passing a value as the third argument to :py:func:`~thr.redis2http.limits.add_max_limit`, we
repeat the second argument, then the limit will be applied on requests for
which the function returns the same value. Let's change our ``redis2http``
configuration accordingly:


.. literalinclude:: ../examples/limits/redis2http_conf_dynamic_limit.py


The Apache benchmarking tool won't allow us to set dynamic headers so we're
going to write a small Python script using the Tornado asynchronous client to
send ten concurrent requests with ten different values for the ``Foo`` header:

.. literalinclude:: ../examples/limits/dynamic_header_benchmark.py

Let's measure its execution time::


    $ time python dynamic_header_benchmark.py 

    real    0m1.235s
    user    0m0.106s
    sys 0m0.093s

Since each request has a different value for the ``Foo`` header, no limit is applied and all ten requests are served concurrently. If however we send the same header with each request, we observe that the limit of two simultaneous requests is applied::

    $ ab -c10 -n10 -H "Foo: baz" http://127.0.0.1:8888/|grep 'Time taken'
    Time taken for tests:   5.051 seconds
