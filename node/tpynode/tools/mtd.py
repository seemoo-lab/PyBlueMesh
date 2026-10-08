# -*- coding: utf-8 -*-
# @Author: Daniel Steinmetzer
# @Date:   2018-03-28 15:59:58
# @Last Modified by:   Daniel Steinmetzer
# @Last Modified time: 2018-03-29 08:46:22

import logging
import re

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class mtd(object):

    @classmethod
    def get_partitions(cls):
        with open('/proc/mtd', mode='r') as file:
            data = file.read()
        rx = re.compile(
            '(mtd\d+)\:\s+([0-9a-fA-F]{8})' +
            '\s+([0-9a-fA-F]{8})\s+\"([a-zA-Z0-9\-_]+)\"')
        m = rx.findall(data)
        return m

    @classmethod
    def get_default_mac(cls):
        partitions = cls.get_partitions()
        dev = [x[0] for x in partitions if x[3] == 'default-mac'][0]
        with open('/dev/%s' % dev, mode='rb') as file:
            content = file.read()
        return ':'.join('{:02x}'.format(x) for x in content[8:14])

    @classmethod
    def get_device_id(cls):
        partitions = cls.get_partitions()
        dev = [x[0] for x in partitions if x[3] == 'device-id'][0]
        with open('/dev/%s' % dev, mode='rb') as file:
            content = file.read()
        return content[8:55].decode()

    @classmethod
    def get_product_info(cls):
        partitions = cls.get_partitions()
        dev = [x[0] for x in partitions if x[3] == 'product-info'][0]
        with open('/dev/%s' % dev, mode='rb') as file:
            data = file.read()
        content = bytearray([x for x in data if not x == 255 and not x == 0])
        return content[1:].decode()
