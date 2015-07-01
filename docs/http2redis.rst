http2redis configuration
------------------------

http2redis must be configured with a Python script based on a simple API. You just need
to know about one function and two classes to get started. The :func:`~thr.http2redis.rules.add_rule` function
is used to create a new rule. :func:`~thr.http2redis.rules.add_rule` takes two mandatory
parameters: an instance of the :py:class:`~thr.http2redis.rules.Criteria` class and an instance of the
:py:class:`~thr.http2redis.rules.Actions` class.  You may also use the optional :keyword:`stop` keyword argument to
tell THR that if a request matches the rule, it should ignore subsequent rules for that request.

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


