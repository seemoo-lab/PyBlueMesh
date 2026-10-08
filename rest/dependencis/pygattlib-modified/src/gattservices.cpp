// -*- mode: c++; coding: utf-8; tab-width: 4 -*-

// Copyright (C) 2014, Oscar Acena <oscaracena@gmail.com>
// This software is under the terms of Apache License v2 or later.

#include <bluetooth/bluetooth.h>
#include <bluetooth/hci.h>
#include <bluetooth/hci_lib.h>

extern "C" {
	#include "lib/uuid.h"
}

#include <exception>

#include "gattlib.h"
#include "gattservices.h"

#include <stdio.h>

DiscoveryService::DiscoveryService(const std::string device) :
	_device(device),
	_device_desc(-1) {

	int dev_id = hci_devid(device.c_str());
	if (dev_id < 0)
		throw std::runtime_error("Invalid device!");

	_device_desc = hci_open_dev(dev_id);
	if (_device_desc < 0)
		throw std::runtime_error("Could not open device!");
	}

DiscoveryService::~DiscoveryService() {
	if (_device_desc != -1)
		hci_close_dev(_device_desc);
}

void
DiscoveryService::enable_scan_mode() {
	int result;
	uint8_t scan_type = 0x01;
	uint16_t interval = htobs(0x0010);
	uint16_t window = htobs(0x0010);
	uint8_t own_type = 0x00;
	uint8_t filter_policy = 0x00;

	result = hci_le_set_scan_parameters
		(_device_desc, scan_type, interval, window,
		 own_type, filter_policy, 10000);

	if (result < 0)
		throw std::runtime_error
			("Set scan parameters failed (are you root?)");

	result = hci_le_set_scan_enable(_device_desc, 0x01, 1, 10000);
	if (result < 0)
		throw std::runtime_error("Enable scan failed");
}

void
DiscoveryService::get_advertisements(int timeout, boost::python::dict & ret, bool getAll){
	struct hci_filter old_options;
	socklen_t slen = sizeof(old_options);
	if (getsockopt(_device_desc, SOL_HCI, HCI_FILTER,
				   &old_options, &slen) < 0)
		throw std::runtime_error("Could not get socket options");

	struct hci_filter new_options;
	hci_filter_clear(&new_options);
	hci_filter_set_ptype(HCI_EVENT_PKT, &new_options);
	hci_filter_set_event(EVT_LE_META_EVENT, &new_options);

	if (setsockopt(_device_desc, SOL_HCI, HCI_FILTER,
				   &new_options, sizeof(new_options)) < 0)
		throw std::runtime_error("Could not set socket options\n");

	int len;
	unsigned char buffer[HCI_MAX_EVENT_SIZE];
	struct timeval wait;
	fd_set read_set;
	wait.tv_sec = timeout;
	int ts = time(NULL);

	while(1) {
		FD_ZERO(&read_set);
		FD_SET(_device_desc, &read_set);

		int err = select(FD_SETSIZE, &read_set, NULL, NULL, &wait);
		if (err <= 0)
			break;

		len = read(_device_desc, buffer, sizeof(buffer));
        
		if (getAll)
		{
			process_all_input(buffer, len, ret);
		}
		else
		{
			process_input(buffer, len, ret);
		}

		int elapsed = time(NULL) - ts;
		if (elapsed >= timeout)
			break;

		wait.tv_sec = timeout - elapsed;
	}

	setsockopt(_device_desc, SOL_HCI, HCI_FILTER,
			   &old_options, sizeof(old_options));
}

void
DiscoveryService::process_input(unsigned char* buffer, int size,
		boost::python::dict & ret){
	unsigned char* ptr = buffer + HCI_EVENT_HDR_SIZE + 1;
	evt_le_meta_event* meta = (evt_le_meta_event*) ptr;

	if (meta->subevent != 0x02 || (uint8_t)buffer[BLE_EVENT_TYPE] != BLE_SCAN_RESPONSE)
		return;

	le_advertising_info* info;
	info = (le_advertising_info*) (meta->data + 1);

	char addr[18];
	ba2str(&info->bdaddr, addr);

	std::string name = parse_name(info->data, info->length);
	ret[addr] = name;
}

void
DiscoveryService::process_all_input(unsigned char* buffer, int size,
		boost::python::dict & ret){
	unsigned char* ptr = buffer + HCI_EVENT_HDR_SIZE + 1;
	evt_le_meta_event* meta = (evt_le_meta_event*) ptr;

	if (meta->subevent != 0x02 || (uint8_t)buffer[BLE_EVENT_TYPE] != 0x0)
		return;

	le_advertising_info* info;
	info = (le_advertising_info*) (meta->data + 1);

	char addr[18];
	ba2str(&info->bdaddr, addr);

	ret[addr] = parse_uuid(info->data, info->length);
}

std::string
DiscoveryService::parse_name(uint8_t* data, size_t size) {
	size_t offset = 0;
	std::string unknown = "";

	while (offset < size) {
		uint8_t field_len = data[0];
		size_t name_len;

		if (field_len == 0 || offset + field_len > size)
			return unknown;

		switch (data[1]) {
		case EIR_NAME_SHORT:
		case EIR_NAME_COMPLETE:
			name_len = field_len - 1;
			if (name_len > size)
				return unknown;

			return std::string((const char*)(data + 2), name_len);

		}

		offset += field_len + 1;
		data += field_len + 1;
	}

	return unknown;
}

boost::python::list 
DiscoveryService::get_uuids_list(const uint8_t *data, uint8_t data_len, uint8_t size, uint8_t usecase){
    uint8_t count = data_len / size;

    unsigned int i ;

    boost::python::list uuids;


    bt_uuid_t btuuid;   
    char uuid_hex[MAX_LEN_UUID_STR + 1];

    switch (usecase){
        case EIR_UUID16_ALL:{
            for(i = 0; i < count; i++){
                uuid_hex[MAX_LEN_UUID_STR] = '\0';
                uint16_t uuid = bt_get_le16(data + (i*2));
                bt_uuid16_create(&btuuid, uuid);
                bt_uuid_to_string(&btuuid, uuid_hex, sizeof(uuid_hex));
                uuids.append(uuid_hex);
            }
            break;
        }
        case EIR_UUID32_ALL: {
            for(i = 0; i < count; i++){
                uuid_hex[MAX_LEN_UUID_STR] = '\0';
                uint32_t uuid = bt_get_le32(data + (i*4));
                bt_uuid32_create(&btuuid, uuid);
                bt_uuid_to_string(&btuuid, uuid_hex, sizeof(uuid_hex));
                uuids.append(uuid_hex);
            }
            break;
        }
        case EIR_UUID128_ALL:{
            for(i = 0; i < count; i++){
                uuid_hex[MAX_LEN_UUID_STR] = '\0';
                const uint8_t *uuid = data + (i * 16);
                uuids.append(bt_get_le32(&uuid[12]));
                uuids.append(bt_get_le16(&uuid[10]));
                uuids.append(bt_get_le16(&uuid[8]));
                uuids.append(bt_get_le16(&uuid[6]));
                uuids.append(bt_get_le32(&uuid[2]));
                uuids.append(bt_get_le16(&uuid[0]));
            }
            break;
        }
    }

    return uuids;
}

boost::python::dict  
DiscoveryService::parse_uuid(uint8_t* data, size_t size){
    size_t offset = 0;

    boost::python::dict ret;
    
    while (offset < size) {
        uint8_t field_len = data[0];
        const uint8_t *eir = &data[2];
        size_t data_len;

        if (field_len == 0 || offset + field_len > size)
            break;

        data_len = field_len - 1;

        switch (data[1]) {
            case EIR_FLAGS:{
                uint8_t flags;
                flags = *eir;
                char buffer [data_len + 1];
                sprintf(buffer, "0x%2.2x", flags);
                boost::python::list small_data;
                small_data.append(std::string(buffer));
                ret["FLAGS"] = small_data;
            }
            case EIR_UUID16_ALL: {
                if(data_len < sizeof(uint16_t))
                    break;
                ret["UUID16"] = get_uuids_list(eir, data_len, sizeof(uint16_t), EIR_UUID16_ALL);
                break;
            }
            case EIR_UUID32_ALL: {
                if(data_len < sizeof(uint32_t))
                    break;
                ret["UUID32"] = get_uuids_list(eir, data_len, sizeof(uint32_t), EIR_UUID32_ALL);
                break;
            }
            case EIR_UUID128_ALL:{
                if(data_len < 16)
                    break;
                ret["UUID128"] = get_uuids_list(eir, data_len, 16, EIR_UUID128_ALL);
                break;
            }
            case EIR_SERVICE_UUID16: {
                if(data_len < sizeof(uint16_t))
                    break;
                ret["UUID16_SERVICE"] = get_uuids_list(eir, data_len, sizeof(uint16_t), EIR_UUID16_ALL);
                break;
            }
            case EIR_SERVICE_UUID128: {
                if(data_len < 16)
                    break;
                ret["UUID128_SERVICE"] = get_uuids_list(eir, data_len, 16, EIR_UUID128_ALL);
                break;
            }
            case EIR_NAME_SHORT:
            case EIR_NAME_COMPLETE: {            
                if (data_len > size)
                    break;
                boost::python::list small_data;
                small_data.append(std::string((const char*)(data + 2), data_len));
                ret["NAME"] = small_data;
                break;
            }
            case EIR_TX_POWER:{
                if (data_len < 1)
                    break;
                boost::python::list small_data;
                char buffer [data_len + 1];
                sprintf(buffer, "%d", (int8_t)*eir);
                small_data.append(std::string(buffer));
                ret["TX_POWER"] = small_data ;
                break;
            }

            case EIR_MANUFACTURE_SPECIFIC:{
                if (data_len < 2)
                    break;
                boost::python::list small_data;
                small_data.append(bt_compidtostr(bt_get_le16(eir)));
                ret["COMPANY"] = small_data;
                break;
            }

            case EIR_SERVICE_DATA: {
                if(data_len < 2)
                    break;
                boost::python::list small_data;
                small_data.append(bt_get_le16(&eir[0]));
                ret["SERVICE"] = small_data;
                break;
            }
        }
        offset += field_len + 1;
        data += field_len + 1;
    }

    return ret;
}

void
DiscoveryService::disable_scan_mode() {
	if (_device_desc == -1)
		throw std::runtime_error("Could not disable scan, not enabled yet");

	int result = hci_le_set_scan_enable(_device_desc, 0x00, 1, 10000);
	if (result < 0)
		throw std::runtime_error("Disable scan failed");
}

boost::python::dict
DiscoveryService::discover(int timeout) {
	boost::python::dict retval;
	enable_scan_mode();
	get_advertisements(timeout, retval, false);
	disable_scan_mode();

	return retval;
}

boost::python::dict
DiscoveryService::discover_all(int timeout) {
	boost::python::dict retval;
	enable_scan_mode();
	get_advertisements(timeout, retval, true);
	disable_scan_mode();

	return retval;
}
