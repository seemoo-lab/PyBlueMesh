import Pyro4
import logging
import json
import time
import signal
import sys
import os
from threading import Thread
from datetime import datetime
import socket

from tpynode import TPyModule

import bottle
from bottle import Bottle, ServerAdapter
from bottle import route, run, template, static_file

import bluetooth
from bluetooth.ble import DiscoveryService
from bluetooth.ble import BeaconService
from bluetooth.ble import GATTRequester

from numpy.distutils.fcompiler import str2bool
from _datetime import datetime, timedelta

global_logger = logging.getLogger(__name__)
global_logger.setLevel(logging.DEBUG)

bt = None

class Beacon(object):
    # Beacon class that handles all readable values.

    def __init__(self, data, address):
        self._uuid = data[0]
        self._major = data[1]
        self._minor = data[2]
        self._power = data[3]
        self._rssi = data[4]
        self._address = address
            
class Option(object):
    # Option class that handles an option for auto_testing.
    def __init__(self, option):
        try:
            # Reads the test options.
            self._test_name = option['test_name']
            self._starting_point = datetime.strptime(option['starting_point'], '%d.%m.%Y %H:%M:%S,%f')
            self._end_point = datetime.strptime(option['end_point'], '%d.%m.%Y %H:%M:%S,%f')
            self._test_interval = option['test_interval']
            self._methods = option['methods']
            
            # Convert test interval from string to int. Set interval to 20 seconds if 
            # the string could not be read.
            if str(self._test_interval).__contains__("m"):
                self._test_interval = str(self._test_interval).replace('m', '')
                self._test_interval = int(self._test_interval) * 60
            elif str(self._test_interval).__contains__("s"):
                self._test_interval = str(self._test_interval).replace('s', '')
                self._test_interval = int(self._test_interval)
            else:
                self._test_interval = 20
                
        except Exception as ex:
            global_logger.info('Options of test ' + self._test_name + ' could not be read. ' + str(ex))

class Rest_Bluetooth(TPyModule):
    # The Bluetooth class that is used to get Bluetooth (LE) information.

    def __init__(self, **kwargs):
        super(Rest_Bluetooth, self).__init__(**kwargs)
       
        # Stop advertising before stopping the node.
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        # Test if interactive logging is activated.
        try:
            self._logging = str2bool(kwargs.get('logging'))
        except:
            self._logging = False

        # Test if device name is set.
        try:
            self._device_name = str(kwargs.get('device_name'))
        except:
            self._device_name = socket.gethostname()

        # Test if flag is set.
        try:
            self._flag = str(kwargs.get('flag'))
        except:
            self._flag = ""

        # Test if advertising interval is set.
        try:
            self._advertising_interval = int(kwargs.get('advertising_interval'))
        except:
            self._advertising_interval = 200

        # Test if major value is set.
        try:
            self._major_value = int(kwargs.get('major_value'))
        except:
            self._major_value = 1

        # Test if minor value is set.
        try:
            self._minor_value = int(kwargs.get('minor_value'))
        except:
            self._minor_value  = 1

        # Test if txpower is set.
        try:
            self._tx_power = int(kwargs.get('tx_power'))
        except:
            self._tx_power  = 1

        # Test if beacon uuid is set.
        try:
            self._beacon_uuid = str(kwargs.get('beacon_uuid'))
        except:
            self._beacon_uuid  = "11111111-2222-3333-4444-555555555555"

        # Test if beacon uuid is set.
        try:
            self._packet_uuid = str(kwargs.get('packet_uuid'))
        except:
            self._packet_uuid  = "11111111-2222-3333-4444-555555555555"

        # Test if auto_testing is activated. 
        try:
            self._auto_testing = str2bool(kwargs.get('auto_testing'))
        except:
            self._auto_testing = False

        # Test if auto_advertising packet is activated. 
        try:
            self._auto_advertising_packet = str2bool(kwargs.get('auto_advertising_packet'))
        except:
            self._auto_advertising_packet = False

        # Test if auto_advertising beacon is activated. 
        try:
            self._auto_advertising_beacon = str2bool(kwargs.get('auto_advertising_beacon'))
        except:
            self._auto_advertising_beacon = False

        global bt
        bt = self
         
        # Starts logging if activated.
        if self._logging == True:
            try:
                if not os.path.exists("/usr/logs/bluetooth"):
                    os.makedirs("/usr/logs/bluetooth", 0o777, False)
           
                logger = logging.getLogger("rest_logger")
                logger.setLevel(logging.INFO)
             
                # create a file handler
                handler = logging.FileHandler('/usr/logs/bluetooth/rest.log')
                handler.setLevel(logging.INFO)
         
                # create a logging format
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
         
                # add the handlers to the logger
                logger.addHandler(handler)
            
            except Exception as ex:
                global_logger.info("Could not start logging! " + str(ex))
        
        # Starts auto_testing with the defined options if activated. 
        try:
            if self._auto_testing == True:
                self._test_options = json.loads(kwargs.get('test_options'))
            
                option = None
                    
                for o in self._test_options:
                    option = Option(o)
                    test_thread = Thread(target=self.start_testing, args = (option,))
                    test_thread.setName("Test_Thread " + str(option._test_name))
                    test_thread.daemon = True
                    test_thread.start()

        except Exception as ex:
            global_logger.info("Could not load testing options! " + str(ex))

        # Starts auto_advertising packet if activated.
        if self._auto_advertising_packet == True:
            Rest_Bluetooth.get_ble_advertising_packet()

        # Starts auto_advertising beacon if activated.
        if self._auto_advertising_beacon == True:
            Rest_Bluetooth.get_ble_advertising_beacon()

    def shutdown(self, signal, frame):
        print("Bluetooth class closing!")
        Rest_Bluetooth.stop_ble_advertising_packet()
        Rest_Bluetooth.stop_ble_advertising_beacon()
        sys.exit(0)
       
       
    def start_testing(self, option):
        date_now = datetime.now()
        work = False
        
        if option._end_point < date_now:
            # End of test is already over.
            global_logger.info("Could not start test " + option._test_name + " becuase the endpoint is already over!")
            pass
        elif option._starting_point < date_now:
            # Start of test is over so start tests directly.
            work = True
        else:
            # Wait until the starting time of the test is reached.
            delta = option._starting_point - date_now
            time.sleep(delta.seconds)
            work = True
        
        if work:    
            global_logger.info("Started test " + option._test_name + " with period from " + str(option._starting_point) + " to " + str(option._end_point))
        
            logger = self.create_logger(option._test_name)
            global_logger.info("Started test " + option._test_name + " with period from " + str(option._starting_point) + " to " + str(option._end_point))

            # Starts the testing of all wanted methods in a loop.
            while date_now < option._end_point:            
                methods = {"bluetooth_devices" : Rest_Bluetooth.get_devices, "bluetooth_services" : Rest_Bluetooth.get_services, 
                       "ble_devices" : Rest_Bluetooth.get_ble_devices, "ble_beacons" : Rest_Bluetooth.get_ble_beacons, "ble_devices_all" : Rest_Bluetooth.get_ble_devices_all} 
            
                for method in option._methods:
                    dic = methods[method]()
                    logger.info(json.dumps(dic) + "\n")
            
                time.sleep(option._test_interval)
                date_now = datetime.now()
   
    def create_logger(self, test_name):
     # Creates a logger for every automated test.

        logger = None
        try:
            if not os.path.exists("/usr/logs/bluetooth/tests"):
                os.makedirs("/usr/logs/bluetooth/tests", 0o777, False)
                
            if os.path.exists("/usr/logs/bluetooth/tests/" + test_name + ".log"):
                os.remove("/usr/logs/bluetooth/tests/" + test_name + ".log")
            
        
            logger = logging.getLogger("logger_" + test_name)
            logger.setLevel(logging.INFO)
              
            # create a file handler
            handler = logging.FileHandler('/usr/logs/bluetooth/tests/' + test_name +'.log')
            handler.setLevel(logging.INFO)
          
            # create a logging format
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
          
            # add the handlers to the logger
            logger.addHandler(handler)
                
             
        except Exception as ex:
            global_logger.info("Could not create logger for test " + test_name + "! " + str(ex))

        return logger

######################################################### Bluetooth ########################################################################

    # Gets all bluetooth devices.
    @route('/bluetooth/devices')
    def get_devices():
        devices = bluetooth.discover_devices(lookup_names = True, flush_cache=True, duration=8, lookup_class = True)
        result={'Devices':[]}
        
        major_classes = ( "Miscellaneous", 
                          "Computer", 
                          "Phone", 
                          "LAN/Network Access point", 
                          "Audio/Video", 
                          "Peripheral", 
                          "Imaging" )

        service_classes = ( (16, "positioning"), 
                            (17, "networking"), 
                            (18, "rendering"), 
                            (19, "capturing"),
                            (20, "object transfer"), 
                            (21, "audio"), 
                            (22, "telephony"), 
                            (23, "information"))

        for add, name, dev_cla in devices:
            major_class = (dev_cla >> 8) & 0xf
            
            if major_class < 7:
                major_class = major_classes[major_class]
            else:
                major_class = 'Uncategorized'

            services = []

            for bitpos, classname in service_classes:
                if dev_cla & (1 << (bitpos-1)):
                    services.append(classname)

            result['Devices'].append({'Name' : name, 'Address' : add, 'Type' : major_class, 'Service_classes' : services})

        # Writing log if logging is activated.
        global bt
        if bt._logging:
            logger = logging.getLogger("rest_logger")
            logger.info(json.dumps(result) + "\n\n")
        
        return result
        
    # Gets all bluetooth services.
    @route('/bluetooth/services')
    def get_services():
        services = bluetooth.find_service()
        result={'Services':[]}
        for service in services:
            result['Services'].append(service)
        
        # Writing log if logging is activated.
        global bt
        if bt._logging:
            logger = logging.getLogger("rest_logger")
            logger.info(json.dumps(result) + "\n\n")
            
        return result
    
    # Gets the bluetooth log for interactive method calls.
    @route('/bluetooth/log')
    def get_log():
        return static_file("rest.log", root='/usr/logs/bluetooth/', mimetype='text/log', download="bluetooth.log" )

    # Deletes the bluetooth log for interactive method calls.
    @route('/bluetooth/log/delete')
    def get_log_deleted():
        try:
            if os.path.exists("/usr/logs/bluetooth/rest.log"): 
                os.remove("/usr/logs/bluetooth/rest.log")
                
            return "Log deleted!"
        except:
            return "Log could not be deleted!"

    # Gets the log for planed method test.
    @route('/bluetooth/tests/log/<test_name>')
    def get_test_log(test_name):
        return static_file(test_name + ".log", root='/usr/logs/bluetooth/tests/', mimetype='text/log', download="bluetooth_" + test_name + ".log" )

    # Deletes the log for planed method test.
    @route('/bluetooth/tests/log/<test_name>/delete')
    def get_test_log_deleted(test_name):
        try:
            if os.path.exists("/usr/logs/bluetooth/tests/" + test_name + ".log"): 
                os.remove("/usr/logs/bluetooth/tests/" + test_name + ".log")
                
            return "Log of test " + test_name + " deleted!"
        except:
            return "Log of test " + test_name + " could not be deleted!"

######################################################### Bluetooth Low Energy ########################################################################
    # Gets all BLE devices with address and name.
    @route('/ble/devices')
    def get_ble_devices():
        service = DiscoveryService()
        devices = service.discover(3)

        result={'Devices':[]} 

        for address, name in devices.items():
            result['Devices'].append({'Name': name, 'Address': address})

        # Writing log if logging is activated.
        global bt
        if bt._logging:
            logger = logging.getLogger("rest_logger")
            logger.info(json.dumps(result) + "\n\n")
            
        return result

    # Gets all BLE devices with all advertised information.
    @route('/ble/devices/all')
    def get_ble_devices_all():
        service = DiscoveryService()
        devices = service.discover_all(3)
        
        result = devices

        # Writing log if logging is activated.
        global bt
        if bt._logging:
            logger = logging.getLogger("rest_logger")
            logger.info(json.dumps(result) + "\n\n")
            
        return result

    # Gets all BLE beacons.
    @route('/ble/beacons')
    def get_ble_beacons():
        service = BeaconService()
        devices = service.scan(3)

        result={'Beacons':[]}
        b = None 

        for address, data in list(devices.items()):
            b = Beacon(data, address)
            result['Beacons'].append({'Address': address, 'UUID': b._uuid, 'Major': b._major, 'minor': b._minor, 'Power': b._power, 'RSSI': b._rssi})

        # Writing log if logging is activated.
        global bt
        if bt._logging:
            logger = logging.getLogger("rest_logger")
            logger.info(json.dumps(result) + "\n\n")
            
        return result

    # Starts BLE beacon advertising.
    @route('/ble/advertise/beacon')
    def get_ble_advertising_beacon():
        global bt
        bt.beacon_service = BeaconService()
        # Start_advertising_beacon has this options: 
        # start_advertising(uuid, major = 1 to 65535, minor = 1 to 65535, txpower = -40 to 4, interval = 1 to * in seconds).                                               
        bt.beacon_service.start_advertising(bt._beacon_uuid, bt._major_value, bt._minor_value, bt._tx_power, bt._advertising_interval)
        return "Advertising beacon OK"

    # Stops BLE beacon advertising.
    @route('/ble/advertise/beacon/stop')
    def stop_ble_advertising_beacon():
        global bt
        bt.beacon_service.stop_advertising()
        return "Advertising beacon stopped!"

    # Starts BLE packet advertising.
    @route('/ble/advertise/packet')
    def get_ble_advertising_packet():
        global bt
        bt.beacon_service = BeaconService()
        # Start_advertising_packet has this options: 
        # start_advertising(uuid, device_name = set name or hostname(), flag = set flag or "0x1A", txpower = -40 to 4, interval = 1 to * in    seconds).                                               
        bt.beacon_service.start_advertising_packets(bt._packet_uuid, bt._device_name, bt._flag, bt._tx_power, bt._advertising_interval)
        return "Advertising packet OK"

    # Stops BLE packet advertising.
    @route('/ble/advertise/packet/stop')
    def stop_ble_advertising_packet():
        global bt
        bt.beacon_service.stop_advertising()
        return "Advertising packet stopped!"
        
