#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr released under the MIT license.
# See the LICENSE file for more information.

import uuid
import json


def make_unique_id():
    return str(uuid.uuid4()).replace('-', '')


def serialize_http_request(request, body_link=None, dict_to_inject=None):
    """Serializes a tornado HTTPServerRequest.

    Following attributes are used (and only these ones):
    - method
    - path
    - headers
    - remote_ip
    - host
    - body (if body_link is not given)
    - query_arguments

    Args:
        request (HTTPServerRequest): a tornado HTTPServerRequest object.
        body_link (str): if not None, use this as body in the serialization
            result. It's useful when you have a (big) incoming binary body
            and when you have already uploaded somewhere else.
        dict_to_inject (dict): a dict of (string) keys/values to inject
            inside the serialization.

    Returns:
        A string (bytes), the result of the serialization.
    """
    encoded_query_arguments = {}
    for key, values in request.query_arguments.items():
        encoded_query_arguments[key] = [x.decode('utf-8') for x in values]
    res = {"method": request.method,
           "path": request.path,
           "headers": sorted(request.headers.get_all()),
           "remote_ip": request.remote_ip,
           "query_arguments": encoded_query_arguments,
           "host": request.host}
    if body_link is not None:
        res['body_link'] = body_link
    else:
        res['body'] = request.body
    if dict_to_inject is not None:
        res['extra'] = dict_to_inject
    return json.dumps(res)


def unserialize_message(message):
    # FIXME
    pass
