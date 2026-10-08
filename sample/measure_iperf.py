# -*- coding: utf-8 -*-
# @Author: Daniel Steinmetzer
# @Date:   2018-04-05 15:43:09
# @Last Modified by:   Daniel Steinmetzer
# @Last Modified time: 2018-05-07 14:11:41

import logging
from collections import OrderedDict
import tpycontrol as tpy
from tabulate import tabulate
import numpy as np

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Load device configuartion from local file system
devices = tpy.Devices('devices.conf')

# Instantiate the controller
tc = tpy.TPyControl(devices)

# Use the first two devices
t_ap = tc.nodes['T05']
t_sta = tc.nodes['T06']

mcs_en_vec_default = 7646
n_repetitions = 1
results = list()

# Reset devices
for name, node in tc.nodes.items():
    if node.hostapd.status():
        node.hostapd.stop()
    if node.wpasupplicant.status():
        node.wpasupplicant.stop()
    if node.wil6210iface.is_up():
        node.wil6210iface.set_down()

for r in range(0, n_repetitions):
    print('\n')
    print('------------------------------------------------------------------')
    print('--- Evaluating Repetition %d of %d' % (r + 1, n_repetitions))
    print('---  AP: %s (%s %s)' % (t_ap.name, '', ''))
    print('--- STA: %s (%s %s)' % (t_sta.name, '', ''))
    print('------------------------------------------------------------------')

    print('Starting interfaces ...')
    t_ap.hostapd.start()
    t_sta.wpasupplicant.start()

    print('Establishing connection ...')
    tpy.utils.wait_for_connectivity(t_ap, t_sta, timeout=10)

    # Disable power saving
    # t_ap.wil6210iface.call_wmi_ps_dev_profile_cfg(1)
    # t_sta.wil6210iface.call_wmi_ps_dev_profile_cfg(1)

    for mcs in range(0, 13):

        stats = dict()
        stats['ap'] = t_ap.wil6210iface.get_hwaddr()
        stats['sta'] = t_sta.wil6210iface.get_hwaddr()
        stats['r'] = r
        stats['mcs'] = mcs

        # Adjust RS
        print('Exploring MCS %d ...' % mcs)
        mask = (1 << (mcs + 1)) - 1
        t_sta.wil6210iface.call_wmi_rs_cfg(
            0, mcs_en_vec=mcs_en_vec_default & mask)

        print('Measure Throughput ...')
        iperf_results = tpy.utils.measure_iperf_throughout(t_ap, t_sta)
        tp = iperf_results['end']['sum_sent']['bits_per_second'] / 1e6
        stats['throughput'] = tp
        stats['iperf_results'] = iperf_results
        results.append(stats)

    t_ap.hostapd.stop()
    t_sta.wpasupplicant.stop()
    t_ap.wil6210iface.set_down()
    t_sta.wil6210iface.set_down()

# -------------------------------------------------------------------------
# --- Compute Iperf statistics --------------------------------------------
# -------------------------------------------------------------------------

statistics = list()
collected = [[r for r in results if r['mcs'] == m]
             for m in list(set([x['mcs'] for x in results]))]
for data in collected:
    my_results = dict()
    iperf_data = [d['iperf_results'] for d in data]
    intervals = [x['sum']['bits_per_second'] for ires in iperf_data
                 for x in ires['intervals'] if not x['sum']['omitted'] and
                 x['sum']['seconds'] > 0.9]
    totals = [ires['end']['sum_sent']['bits_per_second'] / 1e6
              for ires in iperf_data]
    percentiles = np.percentile(intervals, [2.5, 50, 97.5]) / 1e6
    my_results['mcs'] = data[0]['mcs']
    my_results['bps_low'] = percentiles[0]
    my_results['bps_median'] = percentiles[1]
    my_results['bps_mean'] = np.mean(intervals) / 1e6
    my_results['bps_high'] = percentiles[2]
    statistics.append(my_results)


print(tabulate(statistics, headers='keys'))


def print_results_excerpt(data, keys):
    filtered = [OrderedDict([(k, r[k]) for k in keys]) for r in results]
    print(tabulate(filtered, headers='keys'))


print_results_excerpt(results, ['ap', 'sta', 'r', 'mcs', 'throughput'])
