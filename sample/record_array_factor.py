# -*- coding: utf-8 -*-
# @Author: Daniel Steinmetzer
# @Date:   2018-04-05 15:43:09
# @Last Modified by:   Daniel Steinmetzer
# @Last Modified time: 2018-05-11 15:43:31


import logging
import tpycontrol as tpy
from tabulate import tabulate
import numpy as np
import matplotlib.pyplot as plt
# from collections import OrderedDict

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load device configuration from local file system
devices = tpy.Devices('devices.conf')

# Instantiate the controller
tc = tpy.TPyControl(devices)

# Use the first two devices
t_ap = tc.nodes['T05']
t_sta = tc.nodes['T15']

stats = dict()

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

print('Obtaining Link quality ')
stats['signal_regular_uplink'] =\
    tpy.utils.fetch_signal_strength(t_ap, t_sta)
stats['signal_regular_downlink'] =\
    tpy.utils.fetch_signal_strength(t_sta, t_ap)
print('Obtained Regular Signal: %d dBm (up), %d dBm (down)' %
      (stats['signal_regular_uplink'], stats['signal_regular_downlink']))

print('Collecting sweep dump ...')
sweep_dump = tpy.utils.collect_sweep_dump_with_traffic(t_ap, t_sta,
                                                       num_sweeps=30)
sweepinfo = tpy.utils.parse_sweep_dump(sweep_dump)

print(tabulate(sweepinfo['results_ap'], headers='keys'))

# print('Measure Regular Throughput ...')
# iperf_results = tpy.utils.measure_iperf_throughout(t_ap, t_sta)
# tp = iperf_results['end']['sum_sent']['bits_per_second'] / 1e6
# stats['throughput_regular'] = tp
# print(tp)

# Determine the best sectors
sid_legacy = [x['sector'] for x in sorted(sweepinfo['results_ap'],
                                          key=lambda k: k['snr_median'])][-3:]
stats['sector_regular'] = sid_legacy
print('using legacy sectors %s' % stats['sector_regular'])

# Copy definition of best legacy sectors
sectors_legacy =\
    [t_sta.wil6210iface.get_rf_tx_sector_config(sid) for sid in sid_legacy]
for idx, sector in enumerate(sectors_legacy):
    t_sta.wil6210iface.set_rf_tx_sector_config(0 + idx, sector)

print('------------------------------------------------------------------')
print('Setting Element-wise Antenna Sectors ...')
print('------------------------------------------------------------------')

# Apply Element Patterns
tpy.utils.apply_separate_elements(t_sta, 32)
t_sta.wil6210iface.select_enabled_tx_sectors([0, 1, 2] + [s for s in range(32, 64)], 0)

print('Collecting sweep dump ...')
sweep_dump_elements = tpy.utils.collect_sweep_dump_with_traffic(t_ap, t_sta)
sweepinfo_elements = tpy.utils.parse_sweep_dump(sweep_dump_elements)

print(tabulate(sweepinfo_elements['results_ap'], headers='keys'))

print('Obtaining Link quality ...')
stats['signal_elem_uplink'] =\
    tpy.utils.fetch_signal_strength(t_ap, t_sta)
stats['signal_elem_downlink'] =\
    tpy.utils.fetch_signal_strength(t_sta, t_ap)
print('Obtained Elementary Signal: %d dBm (up), %d dBm (down)' %
      (stats['signal_elem_uplink'], stats['signal_elem_downlink']))


# Determine the best element and use them as baseline
ae_order = [x['sector'] - 32 for x in sorted(
    sweepinfo_elements['results_ap'], key=lambda k: k['snr_median'])
    if x['sector'] >= 32]
ae_order.reverse()

ae_ref = ae_order[0]
ae_chunks = [ae_order[i:i + 11] for i in range(1, 32, 11)]

cgains = np.full([32, 0], np.complex(np.nan))

for ae_chunk in ae_chunks:
    # Generate the codebook
    codebook = tpy.utils.generate_array_factor_probing_codebook(
        ae_ref, ae_chunk)
    tpy.utils.apply_codebook(t_sta, codebook, 3)
    t_sta.wil6210iface.select_enabled_tx_sectors(
        [s for s in range(0, len(codebook) + 3)], 0)

    sweep_dump = tpy.utils.collect_sweep_dump_with_traffic(
        t_ap, t_sta, num_sweeps=30)

    sweepinfo = tpy.utils.parse_sweep_dump(sweep_dump)
    print('\n')
    print('------------------------------------------------------------------')
    print('---  UPLINK: %s -> %s' % (sweepinfo['sta'], sweepinfo['ap']))
    print('------------------------------------------------------------------')
    print(tabulate(sweepinfo['results_ap'], headers='keys'))

    m = tpy.utils.sweep_dump_matrix(sweep_dump)[3:]
    amp = np.power(10, m / 10)
    ae_list = list(set([cb['ae'] for cb in codebook]))
    c = np.full([32, m.shape[1]], np.complex(np.nan))

    # Now comes the interesting part .. obtain the array factor ...
    for ae in ae_list:
        if ae == ae_ref:
            idx_base = [idx for idx, cb in enumerate(codebook)
                        if cb['ae'] == ae and cb['base']]
            if len(idx_base) != 1:
                logger.error('Invalid parsing elements')
                continue
            cgain = amp[idx_base]

        else:
            idx_base = [idx for idx, cb in enumerate(codebook)
                        if cb['ae'] == ae and cb['base']]
            idx_circ = [idx for idx, cb in enumerate(codebook)
                        if cb['ae'] == ae and not cb['base']]

            if len(idx_base) != 1 or len(idx_circ) != 4:
                logger.error('Invalid parsing elements')
                continue

            f = np.fft.fft(amp[idx_circ], axis=0)
            cgain = amp[idx_base] * np.exp(np.angle(f[1]) * 1j)
        c[ae] = cgain
    cgains = np.append(cgains, c, axis=1)

# Normalize the complex gains
cgains_norm = cgains / cgains[ae_ref]


#     for n in enumerate(ae_list):
nrow = 4
ncol = 8
fig, axs = plt.subplots(nrows=nrow, ncols=ncol)

for idx, ax in enumerate(axs.reshape(-1)):
    ax.set_title('Antenna %d' % idx)
    ax.set_ylim(-1, 1)
    ax.set_xlim(-1, 1)
    ax.scatter(np.real(cgains_norm[idx]), np.imag(cgains_norm[idx]))


# Find a general sector configuration
filt = np.invert(np.all(np.isnan(cgains_norm), axis=1))
bp = np.zeros(32) * 1j
bp[filt] = np.nanmean(cgains_norm[filt], axis=1)
bp = np.conj(bp)
# bp = np.conj(np.nanmean(cgains_norm, axis=1))
psh = np.int_(np.round(np.angle(bp) / np.pi * 2)) % 4

sector = {
    'dtype': [6] * 8,
    'etype': (filt * 2).tolist(),
    'psh': psh.tolist(),
    'x16': 48
}
optimized_sector = sector
t_sta.wil6210iface.set_rf_tx_sector_config(3, sector)
t_sta.wil6210iface.select_enabled_tx_sectors([0, 1, 2, 3], 0)

sweep_dump = tpy.utils.collect_sweep_dump_with_traffic(
    t_ap, t_sta, num_sweeps=30)
sweepinfo = tpy.utils.parse_sweep_dump(sweep_dump)
print(tabulate(sweepinfo['results_ap'], headers='keys'))

print('Obtaining Link Quality with optimization ...')
stats['signal_uplink'] =\
    tpy.utils.fetch_signal_strength(t_ap, t_sta)
stats['signal_downlink'] =\
    tpy.utils.fetch_signal_strength(t_sta, t_ap)
print('Obtained Signal: %d dBm (up), %d dBm (down)' %
      (stats['signal_uplink'], stats['signal_downlink']))


t_sta.wil6210iface.call_wmi_bf_control(0)
t_ap.wil6210iface.call_wmi_bf_control(0)
print('Measure Throughput with optimization...')
t_sta.wil6210iface.select_enabled_tx_sectors([3], 0)
t_sta.wil6210iface.set_rf_selected_tx_sector(t_ap.wil6210iface.get_hwaddr(), 3)
iperf_results = tpy.utils.measure_iperf_throughout(t_ap, t_sta)
tp = iperf_results['end']['sum_sent']['bits_per_second'] / 1e6
print(tp)
stats['signal_uplink'] =\
    tpy.utils.fetch_signal_strength(t_ap, t_sta)
stats['signal_downlink'] =\
    tpy.utils.fetch_signal_strength(t_sta, t_ap)
print('Obtained Signal: %d dBm (up), %d dBm (down)' %
      (stats['signal_uplink'], stats['signal_downlink']))

print('Measure Throughput without optimization ...')
t_sta.wil6210iface.select_enabled_tx_sectors([0, 1, 2], 0)
t_sta.wil6210iface.set_rf_selected_tx_sector(t_ap.wil6210iface.get_hwaddr(), 2)
iperf_results = tpy.utils.measure_iperf_throughout(t_ap, t_sta)
tp = iperf_results['end']['sum_sent']['bits_per_second'] / 1e6
print(tp)
stats['signal_uplink'] =\
    tpy.utils.fetch_signal_strength(t_ap, t_sta)
stats['signal_downlink'] =\
    tpy.utils.fetch_signal_strength(t_sta, t_ap)
print('Obtained Signal: %d dBm (up), %d dBm (down)' %
      (stats['signal_uplink'], stats['signal_downlink']))

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

for idx, sector in enumerate(sectors_legacy):
    t_sta.wil6210iface.set_rf_tx_sector_config(0 + idx, sector)
t_sta.wil6210iface.set_rf_tx_sector_config(3, optimized_sector)
t_sta.wil6210iface.select_enabled_tx_sectors([0, 1, 2], 0)

print('Obtaining Link quality 1')
stats['signal_regular_uplink'] =\
    tpy.utils.fetch_signal_strength(t_ap, t_sta)
stats['signal_regular_downlink'] =\
    tpy.utils.fetch_signal_strength(t_sta, t_ap)
print('Obtained Regular Signal: %d dBm (up), %d dBm (down)' %
      (stats['signal_regular_uplink'], stats['signal_regular_downlink']))

t_sta.wil6210iface.select_enabled_tx_sectors([3], 0)
print('Obtaining Link quality 2')
stats['signal_regular_uplink'] =\
    tpy.utils.fetch_signal_strength(t_ap, t_sta)
stats['signal_regular_downlink'] =\
    tpy.utils.fetch_signal_strength(t_sta, t_ap)
print('Obtained Regular Signal: %d dBm (up), %d dBm (down)' %
      (stats['signal_regular_uplink'], stats['signal_regular_downlink']))






# print('Measure Throughput ...')
# mcs_en_vec_default = 7646
# results = list()
# for mcs in range(0, 13):

#     stats = dict()
#     stats['ap'] = t_ap.hwaddr
#     stats['sta'] = t_sta.hwaddr
#     stats['mcs'] = mcs

#     # Adjust RS
#     print('Exploring MCS %d ...' % mcs)
#     mask = (1 << (mcs + 1)) - 1
#     t_sta.call_wmi_rs_cfg(0, mcs_en_vec=mcs_en_vec_default & mask)

#     print('Measure Throughput ...')
#     iperf_results = tpy.utils.measure_iperf_throughout(t_ap, t_sta)
#     tp = iperf_results['end']['sum_sent']['bits_per_second'] / 1e6
#     stats['throughput'] = tp
#     stats['iperf_results'] = iperf_results
#     results.append(stats)

# statistics = list()
# collected = [[r for r in results if r['mcs'] == m]
#              for m in list(set([x['mcs'] for x in results]))]
# for data in collected:
#     my_results = dict()
#     iperf_data = [d['iperf_results'] for d in data]
#     intervals = [x['sum']['bits_per_second'] for ires in iperf_data
#                  for x in ires['intervals'] if not x['sum']['omitted'] and
#                  x['sum']['seconds'] > 0.9]
#     totals = [ires['end']['sum_sent']['bits_per_second'] / 1e6
#               for ires in iperf_data]
#     percentiles = np.percentile(intervals, [2.5, 50, 97.5]) / 1e6
#     my_results['mcs'] = data[0]['mcs']
#     my_results['bps_low'] = percentiles[0]
#     my_results['bps_median'] = percentiles[1]
#     my_results['bps_mean'] = np.mean(intervals) / 1e6
#     my_results['bps_high'] = percentiles[2]
#     statistics.append(my_results)


# print(tabulate(statistics, headers='keys'))


# def print_results_excerpt(data, keys):
#     filtered = [OrderedDict([(k, r[k]) for k in keys]) for r in results]
#     print(tabulate(filtered, headers='keys'))

# print_results_excerpt(results, ['ap', 'sta', 'r', 'mcs', 'throughput'])


# # Get the antenna elements for probing
# af_codebook = tpy.utils.generate_array_factor_probing_codebooks(ae_ref, 60)

# sweep_dump_af = list()
# # sweepinfo_af = list()

# for af_cb_chunk in af_codebook:

#     # Measure the sectors sweeps again
#     tpy.utils.apply_codebook(t_sta, af_cb_chunk, 0)
#     t_sta.select_enabled_tx_sectors([s for s in range(0, len(af_cb_chunk))], 0)

#     sweep_dump_af.append(tpy.utils.collect_sweep_dump_with_traffic(
#         t_ap, t_sta, num_sweeps=30))

#     m = tpy.utils.sweep_dump_matrix(sweep_dump)


#     for n, ae in enumerate(ae_list):
#         plt.figure()
#         plt.ylim(-1, 1)
#         plt.xlim(-1, 1)
#         plt.scatter(np.real(c[n]), np.imag(c[n]))




#     # sweepinfo_af.append(tpy.utils.parse_sweep_dump(sweep_dump_af_lo))


# array_factor = list()
# # Compute the array factors
# for chunk in range(0, len(af_codebook)):
#     sweep_dump = sweep_dump_af[chunk]
#     codebook = af_codebook[chunk]

#     m = tpy.utils.sweep_dump_matrix(sweep_dump)
#     amp = np.power(10, m / 10)

#     for ae in set([cb['ae'] for cb in codebook]):
#         idx_base = [idx for idx, cb in enumerate(codebook)
#                     if cb['ae'] == ae and cb['base']]
#         idx_circ = [idx for idx, cb in enumerate(codebook)
#                     if cb['ae'] == ae and not cb['base']]

#         if len(idx_base) != 1 or len(idx_circ) != 4:
#             logger.error('Invalid parsing elements')
#             continue

#         # a_b = amp[idx_base]
#         # a_c = amp[idx_circ]
#         f = np.fft.fft(amp[idx_circ], axis=0)
#         cgain = amp[idx_base] * np.exp(np.angle(f[1]) * 1j)

#         # # Compute the error ...
#         # ff = np.concatenate((f[0:2], np.zeros([4093, m.shape[1]]), f[3:4]), 0)
#         # amp_over = np.real(np.fft.ifft(ff, axis=0))
#         # x = np.array([x for x in range(0, 4)]) / 4
#         # x_over = np.array([x for x in range(0, 4096)]) / 4096

#         # for n in range(0, m.shape[1]):
#         #     plt.figure()
#         #     plt.plot(x, amp[idx_circ][:, n], 'o')
#         #     plt.plot(x_over, amp_over[:, n] * 1024)
#         #     plt.show()
#         array_factor.append({'ae': ae, 'cgain': cgain})


# for af in array_factor:
#     max_amp = np.nanmax(np.abs(af['cgain']))
#     plt.figure()
#     plt.xlim((-max_amp,max_amp))
#     plt.ylim((-max_amp,max_amp))
#     plt.scatter(np.real(af['cgain']), np.imag(af['cgain']))


# f, ax = plt.subplots(1, len(ae_list), sharex='col', sharey='row')
# for n in range (0, len(ae_list)):
#     ax[n].scatter(np.real(c[n]), np.imag(c[n]))

# Merge results again


# for chunk, sweep_dump in enumerate(sweep_dump_af):
#     for swp in sweep_dump['dumps_ap']:
#         swp_update = dict()
#         swp_update.update(swp)
#         swp_update['']
#         merged_sweep_dump['dumps_ap'] = dict()
#         merged_sweep_dump


# Measure the weak sectors again
# tpy.utils.apply_codebook(t_sta, af_codebook[64:], 0)
# t_sta.select_enabled_tx_sectors([s for s in range(0, 64)], 0)

# sweep_dump_af_hi = tpy.utils.collect_sweep_dump_with_traffic(t_ap, t_sta, num_sweeps=30)
# sweepinfo_af_hi = tpy.utils.parse_sweep_dump(sweep_dump_af_hi)

# # # Merge sweep and dump
# merged_results = list()
# for idx, r in enumerate(sweepinfo_af_lo['results_ap']):
#     results = dict()
#     results.update(af_codebook[idx])
#     results.update(r)
#     merged_results.append(results)
# # for idx, r in enumerate(sweepinfo_af_hi['results_ap']):
# #     results = dict()
# #     results.update(af_codebook[idx + 64])
# #     results.update(r)
# #     merged_results.append(results)

# m = tpy.utils.sweep_dump_matrix(sweep_dump_af_lo)

# ae_relations = tpy.utils.generate_array_factor_sector_relations(af_codebook, af_ref)

# for ant


# for ae in range(0, 32):
#     idx = [idx for idx, sdef in enumerate(af_codebook)
#            if sdef['etype'][ae]]
#     idx_base = None
#     idx_circ = list()
#     for i in idx:
#         active_elements = set(np.concatenate(
#             np.nonzero(af_codebook[i]['etype'])))

#         if not idx_base and len(active_elements) == 1:
#             idx_base = i
#             continue

#         if not active_elements.difference({ae, ae_ref}) and\
#            ae_ref in active_elements:
#             idx_circ.append(i)

#     print('%2d: base %d ref: %s' % (ae, idx_base, idx_circ))


# mm = np.nanmean(m, 0)
# m_refined = m.transpose() / mm[:, None] * np.mean(mm)
