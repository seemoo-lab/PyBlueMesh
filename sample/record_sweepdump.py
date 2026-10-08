# -*- coding: utf-8 -*-
# @Author: Daniel Steinmetzer
# @Date:   2018-04-05 15:43:09
# @Last Modified by:   Daniel Steinmetzer
# @Last Modified time: 2018-05-08 13:09:31


import logging
import tpycontrol as tpy
from tabulate import tabulate

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load device configuartion from local file system
devices = tpy.Devices('devices.conf')

# Instantiate the controller
tc = tpy.TPyControl(devices)

# Use the first two devices
t_ap = tc.nodes['T10']
t_sta = tc.nodes['T20']

print('\n')
print('------------------------------------------------------------------')
print('---  AP: %s (%s %s)' % (t_ap.name, '', ''))
print('--- STA: %s (%s %s)' % (t_sta.name, '', ''))
print('------------------------------------------------------------------')

# Reset devices
for name, node in tc.nodes.items():
    if node.hostapd.status():
        node.hostapd.stop()
    if node.wpasupplicant.status():
        node.wpasupplicant.stop()
    if node.wil6210iface.is_up():
        node.wil6210iface.set_down()

print('Starting interfaces ...')
t_ap.hostapd.start()
t_sta.wpasupplicant.start()

print('Establishing connection ...')
tpy.utils.wait_for_connectivity(t_ap, t_sta, timeout=10)

print('Collecting sweep dump ...')
sweep_dump = tpy.utils.collect_sweep_dump_with_traffic(t_ap, t_sta,
                                                       num_sweeps=100)
sweepinfo = tpy.utils.parse_sweep_dump(sweep_dump)

print('\n')
print('------------------------------------------------------------------')
print('---  UPLINK: %s -> %s' % (sweepinfo['sta'], sweepinfo['ap']))
print('------------------------------------------------------------------')
print(tabulate(sweepinfo['results_ap'], headers='keys'))

print('------------------------------------------------------------------')
print('---  DOWNLINK: %s -> %s' % (sweepinfo['ap'], sweepinfo['sta']))
print('------------------------------------------------------------------')
print(tabulate(sweepinfo['results_sta'], headers='keys'))

