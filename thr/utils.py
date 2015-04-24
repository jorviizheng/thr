#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr released under the MIT license.
# See the LICENSE file for more information.

import uuid
import json
import six
import socket
from six.moves.urllib.parse import urlencode
from tornado.httpclient import HTTPRequest
from tornado.httputil import HTTPHeaders


def make_unique_id():
    """Returns a unique id with only alphanumeric chars.

    Returns:
        A unique id (string) with only alphanumeric chars.
    """
    return str(uuid.uuid4()).replace('-', '')


def get_ip():
    """Try to get and return the host ip.

    If the result is 127.0.0.1, None is returned.

    Returns:
        The host ip (string) or None.
    """
    try:
        result = socket.gethostbyname(socket.getfqdn())
        if result != '127.0.0.1':
            return result
    except:
        pass


def serialize_http_request(request, body_link=None, dict_to_inject=None,
                           proxy_ip=None):
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
        proxy_ip (string): if not None, use this value as the last proxy ip
            for X-Forwarded-For header ; if the value is AUTO (default), the
            ip adress will be guess automatically

    Returns:
        A string (str), the result of the serialization.
    """
    encoded_query_arguments = {}
    if six.PY3:
        for key, values in request.query_arguments.items():
            encoded_query_arguments[key] = [x.decode('utf-8') for x in values]
    else:
        encoded_query_arguments = request.query_arguments
    if proxy_ip == "AUTO":
        proxy_ip = get_ip()
    if proxy_ip:
        if 'X-Forwarded-For' in request.headers:
            request.headers['X-Forwarded-For'] += ", %s" % proxy_ip
        else:
            request.headers['X-Forwarded-For'] = "%s, %s" % (request.remote_ip,
                                                             proxy_ip)
    encoded_headers = list(request.headers.get_all())
    res = {"method": request.method,
           "path": request.path,
           "host": request.host}
    if len(encoded_query_arguments) > 0:
        res['query_arguments'] = encoded_query_arguments
    if len(encoded_headers) > 0:
        res['headers'] = encoded_headers
    if body_link is not None:
        res['body_link'] = body_link
    else:
        if len(request.body) > 0:
            res['body'] = request.body
    if dict_to_inject is not None:
        res['extra'] = dict_to_inject
    return json.dumps(res)


def unserialize_request_message(message, force_host=None):
    """Unserializes a request message into a tornado HTTPRequest object.

    Args:
        message (str): the message to unserialize.
        force_host (str): a host:port string to force the "Host:" header
            value.

    Returns:
        A tuple (object, body_link, extra_dict) where:
            - "object" is a HTTPRequest object initialized by the
            unserialization
            - "body_link" (if not None) is the link to the body (in this case,
            the body attribute is not set in the HTTPRequest object and should
            be set after by the caller)
            - "extra_dict" is a dict of extra (not HTTP) keys/values injected
            during serialization

    Raises:
        ValueError: when there is a "unserialize exception".
    """
    body_link = None
    extra_dict = {}
    decoded = json.loads(message)
    if force_host:
        host = force_host
    else:
        host = decoded['host']
    if 'query_arguments' in decoded:
        if six.PY2:
            new_qa = {}
            for key, values in decoded['query_arguments'].items():
                new_qa[key] = [x.encode('utf-8') for x in values]
        else:
            new_qa = decoded['query_arguments']
        query_string = urlencode(new_qa, doseq=True)
        url = "http://%s%s?%s" % (host, decoded['path'], query_string)
    else:
        url = "http://%s%s" % (host, decoded['path'])
    kwargs = {}
    kwargs['headers'] = HTTPHeaders()
    if 'headers' in decoded:
        for k, v in decoded['headers']:
            if k.lower() != 'host':
                kwargs['headers'].add(k, v)
    kwargs['headers']['Host'] = host
    if force_host:
        kwargs['headers']['X-Forwarded-Host'] = decoded['host']
    if 'body_link' in decoded:
        body_link = decoded['body_link']
    else:
        if 'body' in decoded:
            kwargs['body'] = decoded['body']
    request = HTTPRequest(url, method=decoded['method'], **kwargs)
    if 'extra' in decoded:
        extra_dict = decoded['extra']
    return (request, body_link, extra_dict)


def serialize_http_response(response, body_link=None, dict_to_inject=None):
    """Serializes a tornado HTTPResponse object.

    Following attributes are used (and only these ones):
    - body (if body_link is not given)
    - code
    - headers

    Args:
        response (HTTPResponse): a tornado HTTPResponse object.
        body_link (str): if not None, use this as body in the serialization
            result. It's useful when you have a (big) binary body
            and when you have already uploaded somewhere else.
        dict_to_inject (dict): a dict of (string) keys/values to inject
            inside the serialization.
    Returns:
        A string (str), the result of the serialization.
    """
    encoded_headers = list(response.headers.get_all())
    res = {"status_code": response.code,
           "headers": encoded_headers}
    if body_link is not None:
        res['body_link'] = body_link
    else:
        res['body'] = response.body
    if dict_to_inject is not None:
        res['extra'] = dict_to_inject
    return json.dumps(res)


def unserialize_response_message(message):
    """Unserializes a response message.

    Args:
        message (str): the message to unserialize.

    Returns:
        A tuple (status_code, body, body_link, headers, extra_dict) where:
            - "status_code" is the http response status_code
            - "body" is the raw body of the response (or None if there is
                a body link)
            - "body_link" is the body link of the response (or None)
            - "headers" is a HTTPHeaders object (headers of the response)
            - "extra_dict" is a dict of extra (not HTTP) keys/values injected
            during serialization

    Raises:
        ValueError: when there is a "unserialize exception".
    """
    body_link = None
    body = None
    extra_dict = {}
    decoded = json.loads(message)
    if 'body_link' in decoded:
        body_link = decoded['body_link']
    status_code = decoded['status_code']
    if body_link is None:
        body = decoded['body']
    headers = HTTPHeaders()
    for k, v in decoded['headers']:
        headers.add(k, v)
    if 'extra' in decoded:
        extra_dict = decoded['extra']
    return (status_code, body, body_link, headers, extra_dict)
