#!/usr/bin/sh

# Install all dependencies for the pybluez framework
apt-get update
apt-get -y install libbluetooth-dev
apt-get -y install pkg-config 
apt-get -y install libboost-python-dev 
apt-get -y install libboost-thread-dev
apt-get -y install libglib2.0-dev
apt-get -y install libatlas-base-dev

# Install pybluez 
pip3 install pybluez 

# Install pybluez[ble]
cd pygattlib-modified/
make PYTHON_VER=3

pip3 install setuptools
python3 setup.py install
 
