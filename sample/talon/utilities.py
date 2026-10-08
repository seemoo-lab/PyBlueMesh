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
# Last Modified: 2018-07-20

import logging
import numpy as np
import matplotlib.pyplot as plt
import time

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ConnectivityError(Exception):
    pass


def reset_interfaces(nodes):
    for name, node in nodes.items():
        if node.Hostapd.status():
            node.Hostapd.stop()
        if node.WPASupplicant.status():
            node.WPASupplicant.stop()
        if node.WiGigIface.is_up():
            node.WiGigIface.set_down()


def check_ap_station_connectivity(ap, sta):
    if ap.WiGigIface.get_dev_mode() != 'AP':
        raise ConnectivityError('Device %s not configured as AP' % ap.hostname)
    if sta.WiGigIface.get_dev_mode() != 'managed':
        raise ConnectivityError('Device %s not configured as STA' %
                                sta.hostname)
    if not ap.WiGigIface.is_connected_to(sta.WiGigIface.get_hwaddr()) or\
       not sta.WiGigIface.is_connected_to(ap.WiGigIface.get_hwaddr()):
        raise ConnectivityError('Devices %s and %s are not connected' %
                                (ap.hostname, sta.hostname))
    return


def wait_for_connectivity(ap, sta, timeout=10):
    # Check mode configuration
    if not ap.Hostapd.status() or ap.WiGigIface.get_dev_mode() != 'AP':
        raise Exception('Hostapd is not running on AP')
    if not sta.WPASupplicant.status() or \
       sta.WiGigIface.get_dev_mode() != 'managed':
        raise Exception('WPA Supplicant is not running on station')
    ap.WiGigIface.wait_for_peer(sta.WiGigIface.get_hwaddr(), timeout)
    sta.WiGigIface.wait_for_peer(ap.WiGigIface.get_hwaddr(), timeout)


def collect_sweep_dump(ap, sta, timeout=20, num_sweeps=10):

    sweep_dump = dict()
    ap_addr = ap.WiGigIface.get_hwaddr()
    sta_addr = sta.WiGigIface.get_hwaddr()

    sweep_dump['ap'] = ap_addr
    sweep_dump['sta'] = sta_addr
    sweep_dump['timeout'] = timeout
    sweep_dump['num_sweeps'] = num_sweeps
    sweep_dump['dumps_ap'] = list()
    sweep_dump['dumps_sta'] = list()

    # Check connectivity
    connectivity = check_ap_station_connectivity(ap, sta)
    if connectivity:
        raise Exception(connectivity)

    logger.info('Collecting Sweeps for %s' % sta_addr)
    tic = time.time()
    sweep_dump['timestamp'] = tic

    while(True):
        # Collect the Sweep Dump at AP
        dump = ap.WiGigIface.get_sweep_dump()
        if not dump:
            raise Exception('Invalid Dump')
        if sweep_dump['dumps_ap'] and\
           sweep_dump['dumps_ap'][-1][-1]['id'] > dump[-1]['id']:
            raise Exception('Sweep ID to low, something went wrong')
        sweep_dump['dumps_ap'].append(dump)

        # Collect the Sweep Dump at Station
        dump = sta.WiGigIface.get_sweep_dump()
        if not dump:
            raise Exception('Invalid Dump')
        if sweep_dump['dumps_sta']\
           and sweep_dump['dumps_sta'][-1][-1]['id'] > dump[-1]['id']:
            raise Exception('Sweep ID to low, something went wrong')
        sweep_dump['dumps_sta'].append(dump)

        # Check if sufficient data are processed
        length_ap = len(set([ss['id'] for s in sweep_dump['dumps_ap']
                             for ss in s if ss['id'] >
                             sweep_dump['dumps_ap'][0][-1]['id']]))
        length_sta = len(set([ss['id'] for s in sweep_dump['dumps_sta']
                              for ss in s if ss['id'] >
                              sweep_dump['dumps_sta'][0][-1]['id']]))
        if length_ap > num_sweeps and length_sta > num_sweeps:
            # Collected sufficient sweeps, continue
            logger.info('Found sufficient sweeps, stopping')
            sweep_dump['stop'] = 'num_sweeps'
            sweep_dump['duration'] = time.time() - tic
            break

        # Check if we ran out of time
        if time.time() > (tic + timeout):
            logger.info('Timeout, stop collecting sweeps')
            sweep_dump['stop'] = 'timeout'
            sweep_dump['duration'] = timeout
            break

    # Return the collected results
    return sweep_dump


def collect_sweep_dump_with_traffic(t_ap, t_sta, timeout=20, num_sweeps=10):
    # Apply configuration to measure fast ...
    default_bf_config_fast = {
        'bf_trigger_fw': 1,
        'long_term_enable': 1,
        'long_term_update_thr': 1,
        'txss_mode': 1,
        'long_term_trig_timeout_per_mcs': [10] * 13,
        'long_term_mbps_th_tbl': [1] * 13}
    t_sta.WiGigIface.wmi_bf_control(0, **default_bf_config_fast)
    t_ap.WiGigIface.wmi_bf_control(0, **default_bf_config_fast)
    t_ap.WiGigIface.set_ipaddr('192.168.100.1')
    t_sta.WiGigIface.set_ipaddr('192.168.100.2')
    t_ap.IPerf.start_server()
    t_sta.IPerf.start_client_in_background('192.168.100.1', duration=timeout)

    # print('Collecting Sweep Dumps')
    sweep_dump = collect_sweep_dump(t_ap, t_sta, timeout, num_sweeps)

    t_ap.IPerf.stop_server()
    t_sta.IPerf.stop_server()
    return sweep_dump


def parse_sweep_dump(sweep_dump):

    sweep_info = dict()
    sweep_info['ap'] = sweep_dump['ap']
    sweep_info['sta'] = sweep_dump['sta']
    ap_dump = flatten_sweep_dump_entries(sweep_dump['dumps_ap'])
    sta_dump = flatten_sweep_dump_entries(sweep_dump['dumps_sta'])

    sweep_info['results_ap'] = parse_dump(ap_dump, sweep_dump['sta'])
    sweep_info['results_sta'] = parse_dump(sta_dump, sweep_dump['ap'])
    return sweep_info


def parse_dump(dump, addr):
    results = list()
    filtered = [s for s in dump if s['src'] == addr and s['snr'] != 0]
    sectors = set([s['sec'] for s in filtered])
    for sector in sectors:
        values = [s['snr'] for s in filtered if s['sec'] == sector]
        percentiles = np.percentile(values, [2.5, 50, 97.5])
        results.append({
            'sector': sector,
            'snr_low': percentiles[0],
            'snr_high': percentiles[2],
            'snr_median': percentiles[1],
            'snr_mean': np.mean(values),
            # 'values': values,
            'std': np.std(values),
            'num_values': len(values)})
    return results


def flatten_sweep_dump_entries(sweep_dumps, use_most_recent_only=False):
    sweep_info = list()
    min_swp_counter = sweep_dumps[0][-1]['id']
    for dump in sweep_dumps[1:]:
        if use_most_recent_only:
            most_recent_swp = dump[-1]['id']
            min_swp_counter = max(min_swp_counter, most_recent_swp - 1)
        sweep_info.extend([s for s in dump if s['id'] > min_swp_counter])
        min_swp_counter = sweep_info[-1]['id']\
            if sweep_info else min_swp_counter
    return sweep_info


def plot_sweep_dump(sweep_dump):
    ap_dump = flatten_sweep_dump_entries(sweep_dump['dumps_ap'])
    sta_dump = flatten_sweep_dump_entries(sweep_dump['dumps_sta'])

    sectors = set([x['sec'] for x in ap_dump])
    plt.xlabel("sweep number")
    plt.ylabel("SNR [dB]")
    plt.title("Uplink Sweep Results")

    for s in sectors:
        dx = [x['id'] for x in ap_dump if x['sec'] == s]
        dy = [x['snr'] for x in ap_dump if x['sec'] == s]

        if len(set([x['cdown'] for x in ap_dump if x['sec'] == s])) > 1:
            logger.warning('Sweep appears invalid, multiple cdowns for sector')

        plt.plot(dx, dy, '-+', label='sector %d' % s)
    plt.legend()
    plt.show()

    sectors = set([x['sec'] for x in sta_dump])
    plt.xlabel("sweep number")
    plt.ylabel("SNR [dB]")
    plt.title("Downlink Sweep Results")

    for s in sectors:
        dx = [x['id'] for x in sta_dump if x['sec'] == s]
        dy = [x['snr'] for x in sta_dump if x['sec'] == s]

        if len(set([x['cdown'] for x in sta_dump if x['sec'] == s])) > 1:
            logger.warning('Sweep appears invalid, multiple cdowns for sector')

        plt.plot(dx, dy, '-+', label='sector %d' % s)
    plt.legend()
    plt.show()


def sweep_dump_matrix(sweep_dump, sectors='all'):
    ap_dump = flatten_sweep_dump_entries(sweep_dump['dumps_ap'])
    sta_dump = flatten_sweep_dump_entries(sweep_dump['dumps_sta'])
    sectors = set([x['sec'] for x in ap_dump]) if sectors == 'all' else sectors
    swps = np.array(list(set([x['id'] for x in ap_dump])))
    values = np.full([len(sectors), len(swps)], np.nan)
    for sid, s in enumerate(sectors):
        dx = np.array([x['id'] for x in ap_dump if x['sec'] == s])
        dy = np.array([x['snr'] for x in ap_dump if x['sec'] == s])
        idx = np.where(np.in1d(swps, dx))[0]
        values[sid][idx] = dy
    return np.array(values)


def fetch_signal_strength(node, peer, timeout=3):
    tic = time.time()
    while time.time() < (tic + timeout):
        station_dump = [x for x in node.WiGigIface.get_stations()
                        if x['mac'] == peer.WiGigIface.get_hwaddr()]
        if station_dump:
            return station_dump[0]['signal']
    raise TimeoutError('Timeout reading signal strength for device')
