# -*- coding: utf-8 -*-
# @Author: Daniel Steinmetzer
# @Date:   2018-04-05 15:43:09
# @Last Modified by:   Daniel Steinmetzer
# @Last Modified time: 2018-05-07 10:34:25

import logging
from tabulate import tabulate
import tpycontrol as tpy
import time

MAX_ERRORS = 5

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Load device configuartion from local file system
devices = tpy.Devices('devices.conf')

# Instantiate the controller
tc = tpy.TPyControl(devices)

# Reset devices
for name, node in tc.nodes.items():
    if node.hostapd.status():
        node.hostapd.stop()
    if node.wpasupplicant.status():
        node.wpasupplicant.stop()
    if node.wil6210iface.is_up():
        node.wil6210iface.set_down()

# Determine links among devices
links = [(ap, sta) for _, ap in tc.nodes.items()
         for _, sta in tc.nodes.items() if sta != ap]

results = list()

for link_idx, link in enumerate(links):
    t_ap = link[0]
    t_sta = link[1]
    print('\n')
    print('------------------------------------------------------------------')
    print('--- Evaluating Link %d of %d' % (link_idx + 1, len(links)))
    print('---  AP: %s (%s %s)' % (t_ap.name, '', t_ap.wil6210iface.get_hwaddr()))
    print('--- STA: %s (%s %s)' % (t_sta.name, '', t_sta.wil6210iface.get_hwaddr()))
    print('------------------------------------------------------------------')

    # Fetch statistics
    stats = dict()
    stats['ap'] = t_ap.wil6210iface.get_hwaddr()
    stats['sta'] = t_sta.wil6210iface.get_hwaddr()
    success = False

    while not success:
        try:
            print('Starting interfaces ...')
            t_ap.hostapd.start()
            t_sta.wpasupplicant.start()

            print('Establishing connection ...')
            tpy.utils.wait_for_connectivity(t_ap, t_sta, timeout=10)

            print('Obtaining Link quality ...')
            stats['signal_uplink'] =\
                tpy.utils.fetch_signal_strength(t_sta, t_ap)
            stats['signal_downlink'] =\
                tpy.utils.fetch_signal_strength(t_ap, t_sta)
            print('Obtained Signal: %d dBm (up), %d dBm (down)' %
                  (stats['signal_uplink'], stats['signal_downlink']))

        except Exception as e:
            # log = t_ap.get_log()
            # print(log)
            logger.exception(e)
            logger.info('Resetting devices')
            if t_ap.hostapd.status():
                t_ap.hostapd.stop()
            if t_ap.wpasupplicant.status():
                t_ap.wpasupplicant.stop()
            if t_ap.wil6210iface.is_up():
                t_ap.wil6210iface.set_down()
            if t_sta.hostapd.status():
                t_sta.hostapd.stop()
            if t_sta.wpasupplicant.status():
                t_sta.wpasupplicant.stop()
            if t_sta.wil6210iface.is_up():
                t_sta.wil6210iface.set_down()
            time.sleep(1)
        else:
            success = True
            results.append(stats)
        finally:
            print('Stopping interfaces ...')
            t_sta.wpasupplicant.stop()
            t_ap.hostapd.stop()

# Plot results
print(tabulate(results, headers='keys'))
