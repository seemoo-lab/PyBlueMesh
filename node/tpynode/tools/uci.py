#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#          ###########   ###########   ##########    ##########
#         ############  ############  ############  ############
#         ##            ##            ##   ##   ##  ##        ##
#         ##            ##            ##   ##   ##  ##        ##
#         ###########   ####  ######  ##   ##   ##  ##    ######
#          ###########  ####  #       ##   ##   ##  ##    #    #
#                   ##  ##    ######  ##   ##   ##  ##    #    #
#                   ##  ##    #       ##   ##   ##  ##    #    #
#         ############  ##### ######  ##   ##   ##  ##### ######
#         ###########    ###########  ##   ##   ##   ##########
#
#            S E C U R E   M O B I L E   N E T W O R K I N G
#
# Author:        Daniel Steinmetzer
# E-Mail:        dsteinmetzer@seemoo.tu-darmstadt.de
# Website:       https://www.seemoo.de/dsteinmetzer
# Project:       talon-py
# File:          uci.py
# Date:          2018-02-01
# Last Modified: 2018-02-08
#
import logging
import subprocess

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class uci(object):

    @classmethod
    def get(cls, key):
        cmd = ['uci', 'get', key]
        try:
            value = subprocess.check_output(cmd).decode()[:-1]
            logger.info('%s -> %s' % (' '.join(cmd), value))
            return value
        except subprocess.CalledProcessError as e:
            logger.error('%s failed!' % (' '.join(cmd), value))
            logger.exception(e)
            return None

    @classmethod
    def set(cls, key, value):
        cmd = ['uci', 'set', '%s=%s' % (key, value)]
        try:
            value = subprocess.check_output(cmd).decode()
            logger.info('%s' % (' '.join(cmd)))
            return True
        except subprocess.CalledProcessError as e:
            logger.error('%s failed!' % (' '.join(cmd), value))
            logger.exception(e)
            return False

    @classmethod
    def commit(cls):
        try:
            subprocess.check_output(['uci', 'commit'])
            logger.info('uci commit')
        except subprocess.CalledProcessError as e:
            logger.error('uci commit failed!')
            logger.exception(e)
            return False

    @classmethod
    def show(cls, key):
        cmd = ['uci', 'show', key]
        try:
            value = subprocess.check_output(cmd).decode()
            logger.info('%s' % (' '.join(cmd)))
            return value
        except subprocess.CalledProcessError as e:
            logger.error('%s failed!' % (' '.join(cmd), value))
            logger.exception(e)
            return None

    @classmethod
    def backup(cls):
        raise NotImplemented()

    @classmethod
    def restore(cls):
        raise NotImplemented()
