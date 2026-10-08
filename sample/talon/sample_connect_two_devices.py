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
# Website:       https:://www.seemoo.de/dsteinmetzer
# Date:          2018-07-17
# Last Modified: 2018-07-17

import logging
import tpycontrol as tpy
import importlib

# Import utilities
utils = importlib.import_module('utilities')

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEVICES = 'devices.conf'

# Instantiate the controller
tc = tpy.TPyControl(DEVICES)

# Use the first two devices
node_ap = list(tc.nodes.items())[0][1]
node_st = list(tc.nodes.items())[1][1]

print('\n')
print('------------------------------------------------------------------')
print('---  AP: %s (%s)' % (node_ap.hostname, node_ap.host))
print('--- STA: %s (%s)' % (node_st.hostname, node_st.host))
print('------------------------------------------------------------------')

# Reset all devices
print('Resetting all interfaces ...')
utils.reset_interfaces(tc.nodes)

# Start interfaces
print('Starting interfaces ...')
node_ap.Hostapd.start()
node_st.WPASupplicant.start()

print('Waiting for STA to connect to AP ...')
try:
    utils.wait_for_connectivity(node_ap, node_st, timeout=10)
    print('Connection established')
except TimeoutError:
    print('Connection Failed, devices not associated')
