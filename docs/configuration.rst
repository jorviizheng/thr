
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

    add_rule(criteria(method='GET', remote_ip='127.0.0.1', path=regexp('^.*$')),
             actions(set_queue='queue1'))
    add_rule(criteria(method='POST', remote_ip=glob('*.*.*.*'), path='/specific')
             actions(set_status_code=403), stop=1)
    add_rule(criteria(method='POST', remote_ip=glob('*.*.*.*'), path='/specific2'),
             actions(set_status_code=403, set_input_header=('foo', 'bar')), stop=0)
    add_rule(criteria(method='POST', remote_ip=glob('137.129.*.*'), path='/specific'),
             actions(set_status_code=200))
    add_rule(criteria(method='POST', remote_ip=glob('137.129.*.*'), path='/specific2'),
             actions(set_status_code=200))

This file is a succession of rules declared by calling the ``add_rule``
function. ``add_rule`` takes two positional arguments: ``criteria`` and
``actions``.
