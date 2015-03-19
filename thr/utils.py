#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of thr released under the MIT license.
# See the LICENSE file for more information.

import uuid


def make_unique_id():
    return str(uuid.uuid4()).replace('-', '')
