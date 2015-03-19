#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr library released under the MIT license.
# See the LICENSE file for more information.

class HTTPExchange(object):

    def __init__(self, request):
        self.request = request
        self.response = {}
