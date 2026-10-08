def read_station_dump(node, module='AdHocInterface'):
    dump = node[module].iw_station_dump()
    station_list = [s.splitlines() for s in dump.split('Station ')[1:]]
    station_to_dump = {e[0].split(' (on')[0]: e[1:] for e in station_list}
    station_to_properties = {k: {l[0]: l[1].strip() for l in [s.replace('\t', '').split(':') for s in v]} for k, v in station_to_dump.items()}
    return station_to_properties


def read_station_dumps(nodes, module='AdHocInterface'):
    return {name: read_station_dump(node, module=module) for name, node in nodes.items()}


def get_stations(dump):
    return {n: [s for s in d.keys()] for n, d in dump.items()}


def get_stations_above_rssi(dump, threshold=-70):
    return {n: [s for s, p in d.items() if int(p['signal avg'].split()[0]) > -70] for n, d in dump.items()}
