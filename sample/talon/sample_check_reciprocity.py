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
from tabulate import tabulate
import sys

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
    sys.exit(1)

# Force using single sector
sector = 63
sector_config = node_ap.WiGigIface.get_rf_tx_sector_config(sector)
node_ap.WiGigIface.set_rf_rx_sector_config(sector, sector_config)
sector_config = node_st.WiGigIface.get_rf_tx_sector_config(sector)
node_st.WiGigIface.set_rf_rx_sector_config(sector, sector_config)
node_ap.WiGigIface.select_enabled_tx_sectors([sector], 0)
node_st.WiGigIface.select_enabled_tx_sectors([sector], 0)


node_ap.WiGigIface.wmi_ps_dev_profile_cfg(1)
node_st.WiGigIface.wmi_ps_dev_profile_cfg(1)


print('Collecting sweep dump ...')
sweep_dump = utils.collect_sweep_dump_with_traffic(node_ap, node_st,
                                                   timeout=60,
                                                   num_sweeps=100)
sweepinfo = utils.parse_sweep_dump(sweep_dump)

print('\n')
print('------------------------------------------------------------------')
print('---  UPLINK: %s -> %s' % (sweepinfo['sta'], sweepinfo['ap']))
print('------------------------------------------------------------------')
print(tabulate(sweepinfo['results_ap'], headers='keys'))

print('------------------------------------------------------------------')
print('---  DOWNLINK: %s -> %s' % (sweepinfo['ap'], sweepinfo['sta']))
print('------------------------------------------------------------------')
print(tabulate(sweepinfo['results_sta'], headers='keys'))

# Plot the results
utils.plot_sweep_dump(sweep_dump)
