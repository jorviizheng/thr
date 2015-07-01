.. thr documentation master file, created by
   sphinx-quickstart on Tue Sep  9 21:29:37 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. highlight:: python

thr - Tornado HTTP over Redis
=============================

Getting started
---------------

thr is made of two programs:

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


http2redis
~~~~~~~~~~

http2redis must be configured with a Python script based on a simple API. You just need
to know about one function and two classes to get started. The :func:`~thr.http2redis.rules.add_rule` function
is used to create a new rule. :func:`~thr.http2redis.rules.add_rule` takes two mandatory
parameters: an instance of the :py:class:`~thr.http2redis.rules.Criteria` class and an instance of the
:py:class:`~thr.http2redis.rules.Actions` class.  You may also use the optional :keyword:`stop` keyword argument to
tell thr that if a request matches the rule, it should ignore subsequent rules for that request.

.. highlight:: python

Here is an example::

    # myconfig.py

    from thr.http2redis.rules import add_rule, Criteria, Actions

    add_rule(Criteria(path='/forbidden'), Actions(set_status_code=403), stop=1)
    add_rule(Criteria(path='/allowed'), Actions(set_status_code=200))

Using this configuration, any request made to ``/forbidden`` will trigger
a 403 response code. Requests to ``/allowed`` should trigger a 200 response.

To use a configuration file, start ``http2redis`` with the ``--config`` argument::

    $ http2redis --config=myconfig.py 
    Start http2redis on http://localhost:8888

Now you can send requests to verify that the configuration file is taken into acount::

    $ curl -D - http://localhost:8888/forbidden
    HTTP/1.1 403 Forbidden
    [...]

    $ curl -D - http://localhost:8888/allowed
    HTTP/1.1 200 OK
    [...]


API Reference
-------------

.. automodule:: thr

 .. autofunction:: thr.http2redis.rules.add_rule

 .. autoclass:: thr.http2redis.rules.Criteria
     :members:

 .. autoclass:: thr.http2redis.rules.Actions
     :members:

 .. autoclass:: thr.http2redis.rules.glob
     :members:

 .. autoclass:: thr.http2redis.exchange.HTTPExchange
     :members:
 

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
