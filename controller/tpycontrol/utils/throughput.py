def measure_iperf_throughout(server, client, mtu=3000, **kwargs):

    server.wil6210iface.set_ipaddr('192.168.100.1')
    client.wil6210iface.set_ipaddr('192.168.100.2')
    server.wil6210iface.set_mtu(mtu)
    client.wil6210iface.set_mtu(mtu)
    server.IPerf.start_server()
    iperf_results = client.IPerf.start_client('192.168.100.1',
                                              duration=3, omit=2,
                                              parallel_connections=3)

    server.IPerf.stop_server()
    return iperf_results
