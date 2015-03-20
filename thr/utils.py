#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr released under the MIT license.
# See the LICENSE file for more information.

import uuid
import json
from six.moves.urllib.parse import urlencode
from tornado.httpclient import HTTPRequest
from tornado.httputil import HTTPHeaders


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
        A string (str), the result of the serialization.
    """
    encoded_query_arguments = {}
    for key, values in request.query_arguments.items():
        encoded_query_arguments[key] = [x.decode('latin1') for x in values]
    encoded_headers = list(request.headers.get_all())
    res = {"method": request.method,
           "path": request.path,
           "remote_ip": request.remote_ip,
           "host": request.host}
    if len(encoded_query_arguments) > 0:
        res['query_arguments'] = encoded_query_arguments
    if len(encoded_headers) > 0:
        res['headers'] = encoded_headers
    if body_link is not None:
        res['body_link'] = body_link
    else:
        if len(request.body) > 0:
            res['body'] = request.body.decode()
    if dict_to_inject is not None:
        res['extra'] = dict_to_inject
    return json.dumps(res)


def unserialize_message(message, force_host=None):
    """Unserializes a message into a tornado HTTPRequest object.

    Args:
        message (str): the message to unserialize.
        force_host (str): a host:port string to force the "Host:" header
            value.

    Returns:
        A tuple (object, body_link, http_dict, extra_dict) where:
            - "object" is a HTTPRequest object initialized by the
            unserialization
            - "body_link" (if not None) is the link to the body (in this case,
            the body attribute is not set in the HTTPRequest object and should
            be set after by the caller)
            - "http_dict" is a dict of http keys/values not present in the
            HTTPRequest object (for now, keys are "remote_ip",
            "host" (original))
            - "extra_dict" is a dict of extra (not HTTP) keys/values injected
            during serialization

    Raises:
        ValueError: when there is a "unserialize exception".
    """
    body_link = None
    extra_dict = {}
    http_dict = {}
    decoded = json.loads(message)
    if force_host:
        host = force_host
    else:
        host = decoded['host']
    http_dict['host'] = decoded['host']
    http_dict['remote_ip'] = decoded['remote_ip']
    if 'query_arguments' in decoded:
        query_string = urlencode(decoded['query_arguments'], doseq=True)
        url = "http://%s%s?%s" % (host, decoded['path'], query_string)
    else:
        url = "http://%s%s" % (host, decoded['path'])
    kwargs = {}
    if 'headers' in decoded:
        kwargs['headers'] = HTTPHeaders(decoded['headers'])
    if 'body_link' in decoded:
        body_link = decoded['body_link']
    else:
        if 'body' in decoded:
            kwargs['body'] = decoded['body']
    request = HTTPRequest(url, method=decoded['method'], **kwargs)
    if 'extra' in decoded:
        extra_dict = decoded['extra']
    return (request, body_link, http_dict, extra_dict)
