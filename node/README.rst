# TalonPy Node

### Installation

Just run
python3 setup.py sdist

Push file to remote device
scp dist/tpynode-0.0.0-0-d77e06d.tar.gz root@192.168.1.XX:/tmp/

Install on Remote
pip3 install tpynode-0.0.0-0-d77e06d.tar.gz --upgrade

Start
tpynode

# Usage
import Pyro4
talon = Pyro4.Proxy('PYRO:tpynode@%s:42337' % '192.168.1.15')