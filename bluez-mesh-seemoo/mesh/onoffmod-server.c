

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <unistd.h>
#include <stdio.h>
#include <sys/time.h>
#include <ell/ell.h>

#include "mesh/mesh-defs.h"

#include "mesh/mesh.h"
#include "mesh/node.h"
#include "mesh/net.h"
#include "mesh/appkey.h"
#include "mesh/model.h"
#include "mesh/storage.h"

#include "mesh/onoffmod.h"

// Information on net
static struct mesh_net *c_net;

// Current onoff state
static uint8_t onoff_state = 0;

// last TID
static uint8_t last_tid = 0;

// Output file stream for state
static FILE *ofile = NULL;


// Update file with current state.
static void update_file(void)
{
	char state[16];

	if(!ofile) {
		return;
	}

	fseek(ofile, 0, SEEK_SET);
	ftruncate(fileno(ofile), 0);

	int size = snprintf(state, 16, "%d", onoff_state);
	fwrite(state, size, 1, ofile);
	fflush(ofile);

	return;
}

// Process incoming packet
static bool onoff_srv_pkt(uint16_t src, uint32_t dst,
				uint16_t unicast, uint16_t idx,
				const uint8_t *data, uint16_t size,
				uint8_t ttl, const void *user_data)
{
	struct mesh_net *net = (struct mesh_net *) user_data;
	const uint8_t *pkt = data;
	uint32_t opcode;
	uint8_t msg[11];
	struct mesh_net_heartbeat *hb;
	struct mesh_node *node;
	uint16_t n;
	bool send_state = false;

	if (mesh_model_opcode_get(pkt, size, &opcode, &n)) {
		size -= n;
		pkt += n;
	} else
		return false;

	hb = mesh_net_heartbeat_get(net);
	l_debug("ONOFF-SRV-opcode 0x%x size %u idx %3.3x", opcode, size, idx);

	node = mesh_net_local_node_get(net);
	n = 0;

	switch (opcode) {
	default:
		// Unknown packet
		return false;

	case OP_ONOFF_SET:
		// Set with reply
		send_state = true;
		// Fallthrough

	case OP_ONOFF_SET_NOACK:
		// Set without reply
		if (size < 2)
			return false;

		onoff_state = pkt[0];
		last_tid = pkt[1];

		update_file();

		l_debug("OnOff state %d, tid %d", onoff_state, last_tid);
		break;

	case OP_ONOFF_GET:
		send_state = true;
		break;
	}

	if (send_state) {
		// Send reply with state if requested
		n = mesh_model_opcode_set(OP_ONOFF_STATUS, msg);
		msg[n++] = onoff_state;
	}

	if (n) {
		/* print_packet("App Tx", long_msg ? long_msg : msg, n); */
		mesh_model_send(net, ONOFF_SRV_MODEL,
				unicast, src,
				idx, mesh_net_get_default_ttl(c_net),
				msg, n);
	}

	return true;
}

// Clean up model
static void onoffmod_srv_unregister(void *user_data)
{
	struct mesh_net *net = user_data;
	struct mesh_net_heartbeat *hb = mesh_net_heartbeat_get(net);

	l_timeout_remove(hb->pub_timer);
	l_timeout_remove(hb->sub_timer);
	hb->pub_timer = hb->sub_timer = NULL;
}

static const struct mesh_model_ops ops = {
	.unregister = onoffmod_srv_unregister,
	.recv = onoff_srv_pkt,
	.bind = NULL,
	.sub = NULL,
	.pub = NULL
};

// Register model
void mesh_onoff_srv_init(struct mesh_net *net, uint8_t ele_idx)
{
	l_debug("%2.2x", ele_idx);
	mesh_model_register(net, ele_idx, ONOFF_SRV_MODEL, &ops, net);

	c_net = net;
}

// Set output file. Tries to open the file for writing and sets initial state
int mesh_onoff_srv_set_file(const char *file)
{
	char state[16];
	ofile = fopen(file, "w");

	if(!ofile) {
		return -1;
	}

	int size = snprintf(state, 16, "%d", onoff_state);
	fwrite(state, size, 1, ofile);
	fflush(ofile);

	return 0;
}
