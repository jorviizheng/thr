#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

from thr.utils import unserialize_request_message


class HTTPRequestExchange(object):

    def __init__(self, request, queue):
        self.serialized_request = request
        self.queue = queue
        self.__request = None
        self.__body_link = None
        self.__extra_dict = None

    def unserialize_request(self):
        self.__request, self.__body_link, self.__extra_dict = \
            unserialize_request_message(self.serialized_request,
                                        force_host="localhost:8082")  # fix

    @property
    def request(self):
        if not self.__request:
            self.unserialize_request()
        return self.__request

    @property
    def body_link(self):
        if not self.__request:
            self.unserialize_request()
        return self.__body_link

    @property
    def extra_dict(self):
        if not self.__request:
            self.unserialize_request()
        return self.__extra_dict

    @property
    def priority(self):
        if not self.__request:
            self.unserialize_request()
        return self.__extra_dict.get('priority', 5)
