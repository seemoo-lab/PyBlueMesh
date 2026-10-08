#!/usr/bin/sh

# Uninstall all dependencies for the pybluez framework
apt-get update
apt-get -y purge libbluetooth-dev
apt-get -y purge pkg-config 
apt-get -y purge libboost-python-dev 
apt-get -y purge libboost-thread-dev
apt-get -y purge libglib2.0-dev
apt-get -y purge libatlas-base-dev

# Uninstall pybluez 
pip3 uninstall -y pybluez 

# Uninstall pybluez[ble]
cd /usr/local/lib/python3.5/dist-packages

rm -r gattlib-0.20150805-py3.5-linux-armv7l.egg
rm easy-install.pth
 
