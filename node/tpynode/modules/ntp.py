# -*- coding: utf-8 -*-
# @Author: Milan Stute
# @Date:   2018-05-08 12:10:04
# @Last Modified by:   Milan Stute
# @Last Modified time: 2018-05-08 12:10:04

import logging
import Pyro4
import ntplib as ntp

from tpynode import TPyModule

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class NTP(TPyModule):

    def __init__(self, **kwargs):
        super(NTP, self).__init__(**kwargs)
        self._server = kwargs.get('server', None)
        self._client = ntp.NTPClient()

    @Pyro4.expose
    def check_time_offset(self, runs=1, server=None):
        if server is None:
            server = self._server
        if server is None:
            raise RuntimeError('no server given')

        r = [self._client.request(self._server).offset for _ in range(runs)]

        return sum(r) / len(r)
