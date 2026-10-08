/*
 *
 *  BlueZ - Bluetooth protocol stack for Linux
 *
 *  Copyright (C) 2017  Intel Corporation. All rights reserved.
 *
 *
 *  This library is free software; you can redistribute it and/or
 *  modify it under the terms of the GNU Lesser General Public
 *  License as published by the Free Software Foundation; either
 *  version 2.1 of the License, or (at your option) any later version.
 *
 *  This library is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 *  Lesser General Public License for more details.
 *
 *  You should have received a copy of the GNU Lesser General Public
 *  License along with this library; if not, write to the Free Software
 *  Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
 *
 */

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <stdio.h>
#include <errno.h>
#include <unistd.h>
#include <signal.h>
#include <stdlib.h>
#include <stdbool.h>
#include <inttypes.h>
#include <stdbool.h>
#include <sys/uio.h>
#include <wordexp.h>
#include <readline/readline.h>
#include <readline/history.h>
#include <glib.h>

#include "src/shared/shell.h"
#include "src/shared/util.h"
#include "tools/mesh/mesh-net.h"
#include "tools/mesh/keys.h"
#include "tools/mesh/net.h"
#include "tools/mesh/node.h"
#include "tools/mesh/prov-db.h"
#include "tools/mesh/util.h"
#include "tools/mesh/stats-model.h"

#include <ell/ell.h>

// Output file name
static char *output_file = NULL;

// Timeout for receiving packets
static uint32_t batch_timeout = 2;

// Node address to receive information from
static uint32_t target;

// Application key that is bound to the model
static uint16_t stats_app_idx = APP_IDX_INVALID;


// State information for batch receiving
enum batch_record_receive_state {
	IDLE,
	STARTED,
	NUM_RECORDS_RECEIVED,
};

struct batch_record_receive_status {
	int state;
	uint16_t num_records;
	uint16_t current_record;
};

static struct batch_record_receive_status batch_info = {IDLE, 0, 0};

// Callback when an appkey is bound to the model
static int client_bind(uint16_t app_idx, int action)
{
	if (action == ACTION_ADD) {
		if (stats_app_idx != APP_IDX_INVALID) {
			return MESH_STATUS_INSUFF_RESOURCES;
		} else {
			stats_app_idx = app_idx;
			bt_shell_printf("Statistics client model: new binding"
					" %4.4x\n", app_idx);
		}
	} else {
		if (stats_app_idx == app_idx)
			stats_app_idx = APP_IDX_INVALID;
	}
	return MESH_STATUS_SUCCESS;
}

// Send a message to target
static bool send_cmd(uint8_t *buf, uint16_t len, int _ttl)
{
	struct mesh_node *node = node_get_local_node();
	uint8_t ttl;

	if(!node)
		return false;

	if(_ttl == -1) {
		ttl = node_get_default_ttl(node);
	} else {
		ttl = _ttl;
	}

	return net_access_layer_send(ttl, node_get_primary(node),
					target, stats_app_idx, buf, len);
}

// Sends a OP_STATS_GET_RECORD message for record id
static bool send_get_record(uint16_t id)
{
	uint16_t n;
	uint8_t msg[32];

	n = mesh_opcode_set(OP_STATS_GET_RECORD, msg);
	l_put_le16(id, &msg[n]);
	n += 2;

	return send_cmd(msg, n, -1);
}

// Sends a OP_STATS_GET_INFO message
static bool send_get_info(void)
{
	uint16_t n;
	uint8_t msg[32];

	n = mesh_opcode_set(OP_STATS_GET_INFO, msg);

	return send_cmd(msg, n, -1);
}

// Sends a OP_STATS_BEACON message with TTL ttl
static bool send_beacon(int ttl)
{
	uint16_t n;
	uint8_t msg[32];

	n = mesh_opcode_set(OP_STATS_BEACON, msg);

	return send_cmd(msg, n, ttl);
}

// Parse INFO message from server
static void parse_info_reply(uint8_t *data, uint16_t len)
{
	uint16_t n;
	uint8_t msg[32];
	uint16_t num_records = l_get_le16(data);

	bt_shell_printf("Number of records: %d\n", num_records);

	if(batch_info.state == STARTED) {
		// Receiving was started, ask for first record
		batch_info.num_records = num_records;
		batch_info.state = NUM_RECORDS_RECEIVED;

		// Cancel current timeout if pending
		alarm(0);

		// Send message
		send_get_record(batch_info.current_record);

		// Set up timeout
		alarm(batch_timeout);
	}
}

// Record received
static void parse_record_reply(uint8_t *data, uint16_t len)
{
	uint8_t valid;
	uint16_t id;
	uint8_t size;
	uint32_t properties;
	int16_t rssi;
	uint8_t ttl;
	uint16_t duplicateof;
	uint16_t src, dest;

	valid = data[0];

	if(valid != RECORD_VALID) {
		// Record was invalid
		bt_shell_printf("Invalid record received.\n");

		return;
	}

	// Parse packet
	id = l_get_le16(&data[1]);
	size = data[3];
	properties = l_get_le32(&data[4]);
	ttl = data[8];
	rssi = l_get_le16(&data[9]);
	duplicateof = l_get_le16(&data[11]);
	src = l_get_le16(&data[13]);
	dest = l_get_le16(&data[15]);

	// Print properties
	bt_shell_printf("Record %d:\n", id);
	bt_shell_printf("  Size:   %d\n", size);
	bt_shell_printf("  TTL:    %d\n", ttl);
	bt_shell_printf("  RSSI:   %d\n", rssi);
	bt_shell_printf("  DuplOf: %d\n", duplicateof);
	bt_shell_printf("  Src:    %d\n", src);
	bt_shell_printf("  Dest:   %d\n", dest);
	bt_shell_printf("  Properties:\n"
			        "     DUPLICATE:   %d\n"
					"     NOKEY:       %d\n"
					"     PARSEERR:    %d\n"
					"     OWN:         %d\n"
					"     RELAYED:     %d\n",
					!!(properties & STATS_DUPLICATE),
					!!(properties & STATS_NOKEY),
					!!(properties & STATS_PARSEERR),
					!!(properties & STATS_OWN),
					!!(properties & STATS_RELAYED)
			);

	uint16_t n;
	uint8_t msg[32];

	if(batch_info.state == NUM_RECORDS_RECEIVED) {
		// Batch receive ongoing, ask for next packet
		batch_info.current_record++;

		if(batch_info.current_record < batch_info.num_records) {
			// Cancel pending timeout
			alarm(0);
			
			// Ask for next record
			send_get_record(batch_info.current_record);

			// Setup tieout
			alarm(batch_timeout);
		} else {
			// All records received, cancel timeout
			batch_info.state = IDLE;
			alarm(0);
		}
	}
}

// Handle received messages
static bool client_msg_recvd(uint16_t src, uint8_t *data,
				uint16_t len, void *user_data)
{
	uint32_t opcode;
	int n;

	if (mesh_opcode_get(data, len, &opcode, &n)) {
		len -= n;
		data += n;
	} else
		return false;

	bt_shell_printf("Statistics Model Message received (%d) opcode %x\n",
								len, opcode);
	print_byte_array("\t",data, len);

	switch (opcode & ~OP_UNRELIABLE) {
	default:
		return false;

	case OP_STATS_RECORD:
		// Parse record message
		parse_record_reply(data, len);
		break;

	case OP_STATS_INFO:
		// Parse info message
		parse_info_reply(data, len);
		break;
	}

	return true;
}

static uint32_t parms[8];

// Parse parameters of a command issued to the command line parameters. Parses numbers in hex format
static uint32_t read_input_parameters(int argc, char *argv[])
{
	uint32_t i;

	if (!argc)
		return 0;

	--argc;
	++argv;

	if (!argc || argv[0][0] == '\0')
		return 0;

	memset(parms, 0xff, sizeof(parms));

	for (i = 0; i < sizeof(parms)/sizeof(parms[0]) && i < (unsigned) argc;
									i++) {
		sscanf(argv[i], "%x", &parms[i]);
		if (parms[i] == 0xffffffff)
			break;
	}

	return i;
}

// Set target nodes. Called when "target" command was issued
static void cmd_set_node(int argc, char *argv[])
{
	uint32_t dst;
	char *end;

	dst = strtol(argv[1], &end, 16);
	if (end != (argv[1] + 4)) {
		bt_shell_printf("Bad unicast address %s: "
				"expected format 4 digit hex\n", argv[1]);
		target = UNASSIGNED_ADDRESS;
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	} else {
		bt_shell_printf("Controlling stats for node %4.4x\n", dst);
		target = dst;
		set_menu_prompt("stats", argv[1]);
		return bt_shell_noninteractive_quit(EXIT_SUCCESS);
	}
}

// Set timeout. Called when "timeout" command was issued
static void cmd_set_timeout(int argc, char *argv[])
{
	uint32_t timeout;
	char *end;

	if(argc != 2) {
		bt_shell_printf("Please specify timeout in seconds: timeout <seconds>\n");
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	}

	timeout = strtol(argv[1], &end, 10);
	if (timeout == 0) {
		bt_shell_printf("Invalid timeout value.\n");
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	} else {
		bt_shell_printf("Timeout set to %d seconds\n", timeout);
		batch_timeout = timeout;
		return bt_shell_noninteractive_quit(EXIT_SUCCESS);
	}
}

// Send beacon. Called when "beacon" command was issued
static void cmd_send_beacon(int argc, char *argv[])
{
	int ttl;
	char *end;

	if(argc != 2) {
		bt_shell_printf("Please specify TTL: beacon <ttl>\n");
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	}

	ttl = strtol(argv[1], &end, 10);

	send_beacon(ttl);
}

// Set output file name
static void cmd_set_ofile(int argc, char *argv[])
{
	char *end;

	if(argc != 2) {
		bt_shell_printf("Please specify a file: ofile <file>\n");
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	}

	if (strlen(argv[1]) == 0) {
		bt_shell_printf("Invalid file name.\n");
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	} else {
		if(output_file != NULL) {
			free(output_file);
		}

		output_file = malloc(strlen(argv[1]) + 1);
		if(output_file == NULL) {
			bt_shell_printf("Out of memory.\n");
			return bt_shell_noninteractive_quit(EXIT_FAILURE);
		}

		strcpy(output_file, argv[1]);

		bt_shell_printf("Output file set to %s\n", output_file);
		return bt_shell_noninteractive_quit(EXIT_SUCCESS);
	}
}

// Called when a timeout occurs
static void batch_timeout_cb(int signal)
{
	uint16_t n;
	uint8_t msg[32];

	bt_shell_printf("TIMEOUT\n");

	if(batch_info.state == STARTED) {
		// Timeout while getting number of records, try again.
		send_get_info();

		alarm(batch_timeout);
	} else if(batch_info.state == NUM_RECORDS_RECEIVED) {
		// Timeout while getting records, try again.
		send_get_record(batch_info.current_record);

		alarm(batch_timeout);
	}
}

// Called when "records" command was issued
static void cmd_get_records(int argc, char *argv[])
{
	uint16_t n;
	uint8_t msg[32];
	struct mesh_node *node;

	if (IS_UNASSIGNED(target)) {
		bt_shell_printf("Destination not set\n");
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	}

	node = node_find_by_addr(target);

	if (!node)
		return;

	// Set up batch receiving and start timeout
	batch_info.state = STARTED;
	batch_info.num_records = 0;
	batch_info.current_record = 0;
	alarm(batch_timeout);

	// Send info message to get number of records
	if (!send_get_info()) {
		bt_shell_printf("Failed to send \"STATS GET INFO\"\n");
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	}

	return bt_shell_noninteractive_quit(EXIT_SUCCESS);
}

// Called when the "record" command was issued
static void cmd_get_record(int argc, char *argv[])
{
	uint16_t n;
	uint8_t msg[32];
	struct mesh_node *node;

	if (IS_UNASSIGNED(target)) {
		bt_shell_printf("Destination not set\n");
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	}

	node = node_find_by_addr(target);

	if (!node)
		return;

	if ((read_input_parameters(argc, argv) != 1)) {
		bt_shell_printf("Bad arguments: Expecting record id\n");
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	}

	if (!send_get_record(parms[0])) {
		bt_shell_printf("Failed to send \"STATS GET RECORD\"\n");
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	}

	return bt_shell_noninteractive_quit(EXIT_SUCCESS);
}

// Called when the "info" command was issued
static void cmd_get_info(int argc, char *argv[])
{
	uint16_t n;
	uint8_t msg[32];
	struct mesh_node *node;

	if (IS_UNASSIGNED(target)) {
		bt_shell_printf("Destination not set\n");
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	}

	node = node_find_by_addr(target);

	if (!node)
		return;

	if (!send_get_info()) {
		bt_shell_printf("Failed to send \"STATS GET INFO\"\n");
		return bt_shell_noninteractive_quit(EXIT_FAILURE);
	}

	return bt_shell_noninteractive_quit(EXIT_SUCCESS);
}

// Defines all supported commands, their arguments and the callback functions
static const struct bt_shell_menu stats_menu = {
	.name = "stats",
	.desc = "Statistics Model Submenu",
	.entries = {
	{"target",		"<unicast>",			cmd_set_node,
						"Set node to configure"},
	{"record",			"<idx>",			cmd_get_record,
						"Get record <idx>"},
	{"records",			NULL,			cmd_get_records,
							"Get all records"},
	{"beacon",			"<ttl>",			cmd_send_beacon,
								"Send beacon packet with TTL set to <ttl>"},
	{"timeout",		"<seconds>",		cmd_set_timeout,
						"Set transmission timeout"},
	{"ofile",		"<file>",		cmd_set_ofile,
							"Set output file name."},
	{"info",		NULL,			cmd_get_info,
						"Get info"},
	{} },
};

static struct mesh_model_ops client_cbs = {
	client_msg_recvd,
	client_bind,
	NULL,
	NULL
};

// Registers the model and submenu
bool stats_client_init(uint8_t ele)
{
	if (!node_local_vendor_model_register(ele, STATS_CLI_MODEL,
					&client_cbs, NULL))
		return false;

	bt_shell_add_submenu(&stats_menu);

	signal(SIGALRM, batch_timeout_cb);

	return true;
}
