import Pyro4
import logging
import json
import time
import signal
import sys
import os
import stat
import time
from threading import Thread
from datetime import datetime
import socket
import fcntl
import struct
import subprocess

from tpynode import TPyModule

import bottle
from bottle import Bottle, ServerAdapter
from bottle import route, run, template, static_file

from numpy.distutils.fcompiler import str2bool
from _datetime import datetime, timedelta

global_logger = logging.getLogger(__name__)
global_logger.setLevel(logging.DEBUG)

# https://stackoverflow.com/a/24196955
def get_ip_address(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	ret = socket.inet_ntoa(fcntl.ioctl(
		s.fileno(),
		0x8915,  # SIOCGIFADDR
		struct.pack('256s', bytes(ifname[:15],'utf-8'))
	)[20:24])
	
	s.close()
	
	return ret

def get_config_name():
	index = int(get_ip_address("eth0").split(".")[3]) - 1
	
	return "node%.4x.json" % (256 + index)

def start_btmesh(btmesh, rundir, config):
	subprocess.Popen(["/home/pi/start_btmesh.sh", btmesh, rundir, config])

class Rest_Mesh(TPyModule):

	def __init__(self, **kwargs):
		super(Rest_Mesh, self).__init__(**kwargs)
		# Stop btmesh gracefully.
		signal.signal(signal.SIGINT, self.shutdown)
		signal.signal(signal.SIGTERM, self.shutdown)
        
		try:
			self.configfiles = str(kwargs.get('configfiles'))
		except:
			self.configfiles = '/usr/local/lib/python3.5/dist-packages/tpynode-0.0.0+98dc2d4-py3.5.egg/tpynode/data/'
			
		try:
			self.rundir = str(kwargs.get('rundir'))
		except:
			self.rundir = '/media/bluez-testbed/'
			
		try:
			self.btmesh = str(kwargs.get('btmesh'))
		except:
			self.btmesh = '/home/pi/bluez-mesh/build/mesh/btmesh'
		
		start_btmesh(self.btmesh, self.rundir, self.configfiles + get_config_name())
		
		time.sleep(1)
		
		global_logger.info("Waiting for fifo " + self.rundir + "fifo")
		
		while True:
			isfifo = False
			try:
				isfifo = stat.S_ISFIFO(os.stat(self.rundir + "fifo").st_mode)
			except:
				pass
				
			if isfifo:
				break
			else:
				global_logger.info("Waiting for fifo " + self.rundir + "fifo")
				time.sleep(1)
			
		self.cmdfifo = open(self.rundir + "fifo", "w")
		global_logger.info("fifo open")
		
		time.sleep(1)
		
		self.cmdfifo.write("onoff-file onoff.state\n")
		self.cmdfifo.write("stats-file stats.csv\n")
		self.cmdfifo.flush()
		
		global mesh
		mesh = self
	
	def shutdown(self, signal, frame):
		global mesh
		mesh.cmdfifo.write("exit\n")
		mesh.cmdfifo.flush()
		time.sleep(1)
		sys.exit(0)

	# Test API functionality.
	@route('/mesh/api_test')
	def api_test():
		return "Mesh REST-API running!"
		
	# Get btmesh log output.
	@route('/mesh/log')
	def get_log():
		global mesh
		log = open(mesh.rundir + "bluez-log.txt")
		content = log.read()
		log.close()
		return content
		
	# Send onoff packet to server.
	@route('/mesh/onoff/client/<target>/<state>')
	def onoff_send(target, state):
		global mesh
		mesh.cmdfifo.write("onoff-send %s %s\n" % (target, state))
		mesh.cmdfifo.flush()
		global_logger.info("onoff packet sent to %s, state %s" % (target, state))
		return "Ok"
		
	# Get onoff server state.
	@route('/mesh/onoff/server/state')
	def onoff_get_state():
		global mesh
		state = open(mesh.rundir + "onoff.state")
		content = state.read()
		state.close()
		return content
		
	# Get statistics data.
	@route('/mesh/stats/data')
	def stats_get_data():
		global mesh
		stats = open(mesh.rundir + "stats.csv")
		content = stats.read()
		stats.close()
		return content
		
	# Send beacon.
	@route('/mesh/stats/beacon/<target>/<ttl>')
	def stats_beacon(target, ttl):
		global mesh
		mesh.cmdfifo.write("stats-beacon %s %s\n" % (target, ttl))
		mesh.cmdfifo.flush()
		return "Ok"


