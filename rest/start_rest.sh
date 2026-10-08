#!/usr/bin/sh

PASSWORD='rest'

make 
tpy deploy -d rest_devices.conf
tpy restart -d rest_devices.conf 
tpy list -d rest_devices.conf

