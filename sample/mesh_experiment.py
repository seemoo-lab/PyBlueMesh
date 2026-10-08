import logging
import tpycontrol as tpy
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.cm as cm
import pandas as pd
from matplotlib.patches import FancyArrowPatch, Circle
import time


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def graph(df):
    D = nx.DiGraph()
    for s, d, w, b in zip(df['src'], df['name'], df['count'], df['broadcast']):
        D.add_edge(s, d, weight=w, broadcast=b)
    return D


def redraw(df, nodes, **kwargs):
    if len(df) > 0:
        g = df.groupby(['src', 'name'])['broadcast']
        c = g.count().reset_index(name='count')
        c['broadcast'] = (g.sum() / g.count()).reset_index(name='broadcast')['broadcast']
        c['count'] /= c['count'].max()  # normalize
        D = graph(c)
    else:
        D = nx.DiGraph()
    kwargs['ax'].clear()
    D.add_nodes_from(nodes)
    draw_network(D, **kwargs)
    #nx.draw(D, **kwargs)
    return df


def draw_network(G, pos, ax, weight_scale=2, **kwargs):

    nx.draw_networkx_nodes(G, pos, ax=ax, alpha=0.5, **kwargs)

    for n in G:
        c = Circle(pos[n], radius=1, alpha=1, color='white')
        ax.add_patch(c)
        G.node[n]['patch'] = c
    for (u, v, d) in G.edges(data=True):
        n1 = G.node[u]['patch']
        n2 = G.node[v]['patch']

        rad = 0.1
        color = cm.get_cmap('copper')(d['broadcast'])

        e = FancyArrowPatch(n1.center, n2.center,
                            patchA=n1, patchB=n2,
                            arrowstyle='->',
                            connectionstyle='arc3,rad={}'.format(rad),
                            mutation_scale=10.0,
                            color=color,
                            lw=weight_scale * d['weight'])
        ax.add_patch(e)

    nx.draw_networkx_labels(G, pos, ax=ax, **kwargs)

    ax.set_axis_off()
    img = mpimg.imread('cased.png')
    ax.imshow(img, zorder=0, extent=[0, 70, 0, 56])


def get_coordinates(devices):
    coordinates = {}
    for dev in devices:
        name = dev['name']
        coord = dev.get('coordinates')
        if coord is None:
            logger.warning('no coordinates for node {}'.format(name))
            continue
        split = coord.split(',')
        if len(split) < 2:
            logger.warning('need two dimensional coordinates')
            continue
        coordinates[name] = [float(split[0]), float(split[1])]
    return coordinates


def mac_to_name(nodes):
    d = {}
    for name, node in nodes.items():
        mac = node.AdHocInterface.macaddress.upper().replace(':', '-')
        d[mac] = name
    return d


def hostname_to_name(nodes):
    d = {}
    for name, node in nodes.items():
        hostname = node.host
        d[hostname] = name
    return d


def plot_broadcasts_time(df, ax=None):
    if ax is None:
        _, ax = plt.subplots()
    else:
        ax.clear()
    if len(df) == 0:
        return
    dff = df.groupby(['fid', 'k', 'src', 'dst']).first().reset_index()
    dff = dff.groupby(['fid', 'k']).agg({'broadcast': lambda x: x.sum() / x.count(), 'time': 'first'}).reset_index()
    for k, v in dff.groupby('fid'):
        v.plot(x='time', y='broadcast', label=k, ax=ax)
    return dff


def plot_broadcasts(df, ax=None):
    if ax is None:
        _, ax = plt.subplots()
    else:
        ax.clear()
    if len(df) == 0:
        return
    dff = df.groupby(['fid', 'k', 'src', 'dst']).first().reset_index()
    dff = dff.groupby(['fid', 'k']).agg({'broadcast': lambda x: x.sum() / x.count(), 'time': 'first'}).reset_index()
    m = dff.groupby('k')['broadcast'].agg(['median', 'min', 'max']).reset_index()
    ax.fill_between(m.k, m['min'], m['max'], alpha=0.3, label='min-max')
    m.plot(x='k', y='median', ax=ax)
    ax.legend()


def animate(nodes, interval=1.0, decay=10.0):
    animate.active = True

    def handle_close(evt):
        animate.active = False

    c = get_coordinates(devices)
    mac2name = mac_to_name(tc.nodes)
    host2name = hostname_to_name(tc.nodes)

    plt.ion()  # Turn on interactive mode
    df = pd.DataFrame()
    fig, ax = plt.subplots(2)

    cid = fig.canvas.mpl_connect('close_event', handle_close)

    try:
        while animate.active:
            logger.debug('Update plot')
            df = df.append(tpy.read_logs(nodes.values()), sort=False)
            if len(df) > 0:
                df['src'] = df['src'].replace(mac2name)
                df['dst'] = df['dst'].replace(mac2name)
                df['name'] = df['host'].replace(host2name)
                df['broadcast'] = df.dst == 'FF-FF-FF-FF-FF-FF'
                now = time.time()
                dff = df.where(df['time'] >= now - decay)
            else:
                dff = df
            redraw(dff, nodes=nodes.keys(), ax=ax[1], pos=c, arrowsize=20, with_labels=True, node_color='grey', linewidth=1.0, width=2.0)
            plot_broadcasts(dff, ax=ax[0])
            plt.pause(interval)
    except KeyboardInterrupt:
        pass
    finally:
        fig.canvas.mpl_disconnect(cid)
        plt.close(fig)
        return df


def filter_stable_neighbors(nodes, threshold=-70):
    dump = tpy.read_station_dumps(tc.nodes)
    stable_neighbors = tpy.get_stations_above_rssi(dump, threshold=threshold)
    for n, neighbors in stable_neighbors.items():
        tpy.set_active_neighbors(tc.node(n), neighbors)


# Load device configuration from local file system
devices = tpy.Devices('apu.conf')

# Instantiate the controller
tc = tpy.TPyControl(devices)

for h in tc.hosts:
    h.AdHocInterface.down()
    h.AdHocInterface.up()
    h.AdHocInterface.ip_route_flush()
    h.ClickCastor.start('EthDev={}'.format(h.AdHocInterface.iface))
    h.IPerf.start_server()

filter_stable_neighbors(tc.nodes, -70)

logger.info('NTP sync: {}'.format(tpy.check_ntp(tc.nodes)))

logger.info('Start ping')
tc.node('APU03').Ping.ping(tc.node('APU05').AdHocInterface.ipaddress)

df = animate(tc.nodes)
