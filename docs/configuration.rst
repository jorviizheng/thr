
.. _http2redis-conf

Configuration
-------------

http2redis
~~~~~~~~~~

http2redis accepts a configuration file written using a Python domain-specific
language. This file contains a series of rules defined using the `add_rule`
function.

.. highlight:: python

Here is an example::

    add_rule(criteria(method='GET', from='127.0.0.1', path='^.*$'),
             actions(set_queue='queue1'))
    add_rule(criteria(method='POST', from='*.*.*.*', path='/specific')
             actions(set_status_code=403), stop=1)
    add_rule(criteria(method='POST', from='*.*.*.*', path='/specific2'),
             actions(set_status_code=403, set_input_header_foo='bar'), stop=0)
    add_rule(criteria(method='POST', from='137.129.*.*', path='/specific'),
             actions(set_status_code=200))
    add_rule(criteria(method='POST', from='137.129.*.*', path='/specific2'),
             actions(set_status_code=200))
