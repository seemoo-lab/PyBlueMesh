// -*- mode: c++; coding: utf-8; tab-width: 4 -*-

// Copyright (C) 2014, Oscar Acena <oscaracena@gmail.com>
// This software is under the terms of Apache License v2 or later.

#ifndef _GATTSERVICES_H_
#define _GATTSERVICES_H_

#include <boost/python/dict.hpp>
#include <map>

#define EIR_FLAGS                   0x01
#define EIR_NAME_SHORT              0x08
#define EIR_NAME_COMPLETE           0x09
#define EIR_MANUFACTURE_SPECIFIC    0xFF
#define EIR_UUID16_ALL              0x03
#define EIR_UUID32_ALL              0x05
#define EIR_UUID128_ALL             0x07
#define EIR_SERVICE_UUID16          0x14
#define EIR_SERVICE_UUID128         0x15
#define EIR_SERVICE_DATA            0x16
#define EIR_TX_POWER                0x0A
#define EIR_MESH_MSG                0x2A
#define EIR_MESH_BEACON             0x2B


#define BLE_EVENT_TYPE     0x05
#define BLE_SCAN_RESPONSE  0x04

class DiscoveryService {
public:
	DiscoveryService(const std::string device="hci0");
	virtual ~DiscoveryService();
	boost::python::dict discover(int timeout);
	boost::python::dict discover_all(int timeout);


protected:
	void enable_scan_mode();
	void get_advertisements(int timeout, boost::python::dict & ret, bool getAll);
	virtual void process_input(unsigned char* buffer, int size,
			boost::python::dict & ret);
	std::string parse_name(uint8_t* data, size_t size);
	void disable_scan_mode();
	boost::python::list 
		get_uuids_list(const uint8_t *data, uint8_t data_len, uint8_t size, uint8_t usecase);
	boost::python::dict  
		parse_uuid(uint8_t* data, size_t size);
	boost::python::list
		parse_add_fields(uint8_t* data, size_t size);

	void
		process_all_input(unsigned char* buffer, int size, boost::python::dict & ret);

	std::string _device;
	int _device_desc;
	int _timeout;
};

#endif // _GATTSERVICES_H_
