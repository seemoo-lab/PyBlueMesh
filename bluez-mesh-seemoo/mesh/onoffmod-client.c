

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <unistd.h>
#include <stdio.h>
#include <sys/time.h>
#include <ell/ell.h>
#include <fcntl.h>

#include "mesh/mesh-defs.h"

#include "mesh/mesh.h"
#include "mesh/node.h"
#include "mesh/net.h"
#include "mesh/appkey.h"
#include "mesh/model.h"
#include "mesh/storage.h"

#include "mesh/onoffmod.h"

// TID in the packet that was received last
static uint8_t last_tid = 0;

// Information in the net
static struct mesh_net *c_net;
static uint8_t c_ele_idx;
static int bound_app_key = 0;

// Handle packets
static bool onoff_cli_pkt(uint16_t src, uint32_t dst,
				uint16_t unicast, uint16_t idx,
				const uint8_t *data, uint16_t size,
				uint8_t ttl, const void *user_data)
{
	struct mesh_net *net = (struct mesh_net *) user_data;
	const uint8_t *pkt = data;
	uint32_t opcode;
	struct mesh_net_heartbeat *hb;
	struct mesh_node *node;
	uint16_t n;
	uint8_t status;

	if (mesh_model_opcode_get(pkt, size, &opcode, &n)) {
		size -= n;
		pkt += n;
	} else
		return false;

	hb = mesh_net_heartbeat_get(net);
	l_debug("ONOFF-CLI-opcode 0x%x size %u idx %3.3x", opcode, size, idx);

	node = mesh_net_local_node_get(net);

	switch (opcode) {
	default:
		// Unknown opcode
		return false;

	case OP_ONOFF_STATUS:
		// Process reply from server with current status
		status = pkt[0];
		l_debug("OnOff client status %d.", status);
		break;
	}

	return true;
}

// Clean up model
static void onoffmod_cli_unregister(void *user_data)
{
	struct mesh_net *net = user_data;
	struct mesh_net_heartbeat *hb = mesh_net_heartbeat_get(net);

	l_timeout_remove(hb->pub_timer);
	l_timeout_remove(hb->sub_timer);
	hb->pub_timer = hb->sub_timer = NULL;
}

// Save appkey index for sending data
static int onoffmod_cli_bind(uint16_t app_idx, int action)
{
	l_debug("bind app_idx %d action %d", app_idx, action);
	bound_app_key = app_idx;

	return 0;
}

static const struct mesh_model_ops ops = {
	.unregister = onoffmod_cli_unregister,
	.recv = onoff_cli_pkt,
	.bind = onoffmod_cli_bind,
	.sub = NULL,
	.pub = NULL
};

// Send onoff message to address with state enable
void mesh_onoff_cli_set(int address, int enable)
{
	uint16_t n;
	uint8_t msg[11];

	n = mesh_model_opcode_set(OP_ONOFF_SET, msg);
	msg[n++] = enable == 0 ? 0 : 1;
	msg[n++] = last_tid++;

	struct mesh_node *node = mesh_net_local_node_get(c_net);

	mesh_model_send(c_net, ONOFF_SRV_MODEL,
					0, address,
					bound_app_key, mesh_net_get_default_ttl(c_net),
					msg, n);
}

// Register model
void mesh_onoff_cli_init(struct mesh_net *net, uint8_t ele_idx)
{
	l_debug("%2.2x", ele_idx);
	mesh_model_register(net, ele_idx, ONOFF_CLI_MODEL, &ops, net);

	c_net = net;
	c_ele_idx = ele_idx;

	return;
}
