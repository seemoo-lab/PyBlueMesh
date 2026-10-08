import pandas as pd
from threading import Thread
import queue


def read_logs(nodes):
    q = queue.Queue()
    try:
        threads = [Thread(target=read_log, args=(n, q)) for n in nodes]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        df = pd.concat([q.get() for _ in range(q.qsize())], ignore_index=True, sort=False)
    except ValueError:
        return None
    df['k'] = df['k'].astype(int)
    df['time'] = df['time'].astype(float)
    return df


def read_log(node, queue, handler='log.entries'):

    lines = []
    while True:
        r = node.ClickCastor.socket_read(handler)
        rc = int(r[0].split(' ')[0])
        if rc != 200:
            raise ConnectionError('Could not read from socket: {}'.format(r[0]))
        new_lines = r[2].splitlines()
        lines.extend(new_lines)
        # FIXME read limit from Click instance
        if len(new_lines) < 100:
            break

    if len(lines) > 0:
        all = [l.split(' ') for l in lines]
        df = pd.DataFrame(all, columns=['time', 'fid', 'pid', 'k', 'src', 'dst'])
        df['host'] = node.host
        queue.put(df)


def set_active_neighbors(node, neighbors, handler='castorclassifier/neighborFilter'):
    cmds = [(handler + '.clear', ''), (handler + '.active', 'true')]
    for n in neighbors:
        cmds.append((handler + '.add', n))
    return node.ClickCastor.socket_write_batch(cmds)
