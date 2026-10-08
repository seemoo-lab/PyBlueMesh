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

import matplotlib
import matplotlib.pyplot as plt

import matplotlib as mpl
mpl.rcParams['figure.figsize'] = [3.6, 2.0]
mpl.rcParams['savefig.dpi'] = 300
mpl.rcParams['text.usetex'] = True
mpl.rcParams['text.latex.preamble'] = r'\usepackage{libertine},\usepackage[T1]{fontenc}'

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Load device configuartion from local file system
devices = tpy.Devices('devices.conf')

# Instantiate the controller
tc = tpy.TPyControl(devices)

# # Use the first two devices
# t_ap = tc.nodes['T05']
# t_sta = tc.nodes['T06']

mcs_en_vec_default = 7646
n_repetitions = 3
results = list()

# Reset devices
for name, node in tc.nodes.items():
    if node.hostapd.status():
        node.hostapd.stop()
    if node.wpasupplicant.status():
        node.wpasupplicant.stop()
    if node.wil6210iface.is_up():
        node.wil6210iface.set_down()

# # Determine links among devices
# links = [(ap, sta) for _, ap in tc.nodes.items()
#          for _, sta in tc.nodes.items() if sta != ap]

ap = tc.node(0)
links = [(ap, sta)
         for _, sta in tc.nodes.items() if sta != ap]

for link_idx, link in enumerate(links):
    t_ap = link[0]
    t_sta = link[1]

    for r in range(0, n_repetitions):
        print('\n')
        print('------------------------------------------------------------------')
        print('--- Evaluating Link %d of %d with repetition %d of %d' %
              (link_idx + 1, len(links), r + 1, n_repetitions))
        print('---  AP: %s (%s %s)' % (t_ap.name, '', t_ap.wil6210iface.get_hwaddr()))
        print('--- STA: %s (%s %s)' % (t_sta.name, '', t_sta.wil6210iface.get_hwaddr()))
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

srcs = list(set([x['sta'] for x in results]))
dsts = list(set([x['ap'] for x in results]))

all_stats = []

for src in srcs:
    for dst in dsts:
        if dst == src:
            continue

        statistics = list()

        collected = [[r for r in results if r['mcs'] == m and r['ap'] == dst and r['sta'] == src]
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
        all_stats.append(statistics)

        print(tabulate(statistics, headers='keys'))


f = plt.figure()
plt.title('Achievable Throughput')
for stats in all_stats:
    mcs = [x['mcs'] for x in stats]
    y = [x['bps_median'] for x in stats]
    plt.plot(mcs, y)
plt.xlim(0, 12)
plt.xlabel('MCS')
plt.ylabel('Mbps')
plt.show()
f.savefig("results_iperf.pdf", bbox_inches='tight')


def print_results_excerpt(data, keys):
    filtered = [OrderedDict([(k, r[k]) for k in keys]) for r in results]
    print(tabulate(filtered, headers='keys'))


print_results_excerpt(results, ['ap', 'sta', 'r', 'mcs', 'throughput'])
