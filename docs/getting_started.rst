Getting started
---------------

THR is made of two programs:

    * ``http2redis`` takes incoming requests and performs actions on those requests according to rules. One of the most common actions consists in inserting requests into Redis queues that will get consumed by ``redis2http``. When writing a request to a queue, ``http2redis`` specifies on which Redis key it wishes to receive the response and waits for a response on that key.
    * ``redis2http`` reads requests from incoming Redis queues, calls the actual underlying web services and writes responses back to the requested Redis key.

To get started, let's create a minimal web service that responds "Hello World" to any request:

.. literalinclude:: ../examples/hello/app_server.py

Let's create a minimal configuration file for http2redis:


.. literalinclude:: ../examples/hello/http2redis_conf.py

And here is a minial configuration file for redis2http:

.. literalinclude:: ../examples/hello/redis2http_conf.py

.. include:: ../examples/hello/README.rst

The source code for this example can be found in directory ``examples/hello``.
