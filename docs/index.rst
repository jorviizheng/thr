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

http2redis
~~~~~~~~~~

http2redis must be configured with a Python script based on a simple API. You just need
to know one function and two classes to get started. The ``add_rule`` function
is used to create a new rouring rule. ``add_rule`` takes two mandatory
parameters: an instance of the ``Criteria`` class and an instance of the
``Actions`` class.  You may also use the optional ``stop`` keyword argument to
tell thr that if a request matches the rule, it should ignore subsequent rules for this request.

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
    Date: Mon, 30 Mar 2015 15:16:54 GMT
    Content-Length: 0
    Content-Type: text/html; charset=UTF-8
    Server: TornadoServer/4.1

    $ curl -D - http://localhost:8888/allowed
    HTTP/1.1 200 OK
    Date: Mon, 30 Mar 2015 15:16:59 GMT
    Content-Length: 0
    Etag: "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    Content-Type: text/html; charset=UTF-8
    Server: TornadoServer/4.1



Configuration
-------------

* :doc:`/configuration`


API Reference
-------------

.. toctree::
   :maxdepth: 2

.. automodule:: thr

 .. autoclass:: rules.glob
     :members:

 .. autoclass:: rules.Criteria
     :members:
 

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
