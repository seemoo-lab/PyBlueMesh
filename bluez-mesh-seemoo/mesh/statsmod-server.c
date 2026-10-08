

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <unistd.h>
#include <stdio.h>
#include <time.h>
#include <sys/time.h>
#include <ell/ell.h>

#include "mesh/mesh-defs.h"

#include "mesh/mesh.h"
#include "mesh/node.h"
#include "mesh/net.h"
#include "mesh/appkey.h"
#include "mesh/model.h"
#include "mesh/storage.h"

#include "mesh/statsmod.h"

// All data that can be collected for a packet
struct stats_entry {
	uint32_t timestamp;
	int id;
	int rssi;
	uint8_t chan;
	uint16_t size;
	int ttl;
	uint64_t hash;
	int duplicateof;
	uint16_t src;
	uint16_t dest;
	uint8_t opcode;
	// start friend data
	uint8_t win_factor;
	uint16_t prev_friend;
	// end friend data
	uint16_t seq;
	uint8_t nkeyid;
	uint8_t akeyid;
	uint16_t msglen;
	uint8_t *msg;
	uint32_t properties;

	struct stats_entry *next;
};

/* Scaling factors in 1/10 ms */
static const int32_t scalingFriend[] = {
	10,
	15,
	20,
	15,
};

static uint8_t frnd_relay_window = 250;

// Information in the mesh net
static struct mesh_net *c_net;
static int bound_app_key = 0;

// Output file stream
static FILE *ofile = NULL;

// Number of records and start, end of linked list
static uint16_t num_records = 0;
struct stats_entry *first_entry = NULL;
struct stats_entry *last_entry = NULL;

// Adds an entry to the linked list
static void add_stats_entry(struct stats_entry *e)
{
	e->next = NULL;
	e->id = num_records++;
	e->properties = 0;

	if(first_entry == NULL) {
		first_entry = e;
		last_entry = e;

		return;
	}

	last_entry->next = e;
	last_entry = e;

	return;
}

// Add new packet to statistics model
struct stats_entry *mesh_stats_add_packet(void)
{
	struct stats_entry *e = calloc(sizeof(struct stats_entry), 1);

	if(!e) {
		return NULL;
	}

	add_stats_entry(e);

	return e;
}

// Finish handling packet, packet will be written to file.
void mesh_stats_finish_packet(struct stats_entry *p)
{
	int i;
	/*double timestamp;
	struct timespec spec;
	timespec_get(&spec, TIME_UTC);

	timestamp = spec.tv_sec + (spec.tv_nsec / 1.0e9);*/

	struct timeval tm;
	uint32_t timestamp;

	gettimeofday(&tm, NULL);
	timestamp = tm.tv_sec * 10000;
	timestamp += tm.tv_usec / 100;

	if(!p) {
		return;
	}

	//l_debug("finished stats for packet: %d - channel:%i - send timestamp %i - recv timestamp: %i", p->id, p->chan, p->timestamp, timestamp);

	if(ofile) {
		char *hexmsg = calloc((p->msglen * 2) + 1, 1);

		for(i = 0; i < p->msglen; i++) {
			sprintf(hexmsg + (i * 2), "%.2x", p->msg[i]);
		}

		//fprintf(ofile, "%f, %f, %d, %d, %d, %d, %.16llx, %d, %.4x, %.4x, %d, %d, %d, %.8x, %d, %s\n", p->timestamp, timestamp, p->id, p->rssi, p->size, p->ttl, p->hash, p->duplicateof, p->src, p->dest, p->seq, p->nkeyid, p->akeyid, p->properties, p->msglen, hexmsg);
		fprintf(ofile, "%u, %u, %d, %d, %d, %d, %d, %.16llx, %d, %.4x, %.4x, %d,%d,%.4x, %d, %d, %d, %.8x, %d, %s\n", p->timestamp, timestamp, p->id, p->rssi, p->chan, p->size, p->ttl, p->hash, p->duplicateof, p->src, p->dest, p->opcode, p-> win_factor, p->prev_friend, p->seq, p->nkeyid, p->akeyid, p->properties, p->msglen, hexmsg);
		fflush(ofile);
	}

	return;
}

// Below are all functions to set properties.

void mesh_stats_set_chan(struct stats_entry *p, uint8_t chan)
{
	if(!p) {
		return;
	}

	p->chan = chan;

	return;
}

void mesh_stats_set_timestamp(struct stats_entry *p, uint32_t timestamp)
{
	if(!p) {
		return;
	}

	p->timestamp = timestamp;

	return;
}

void mesh_stats_set_rssi(struct stats_entry *p, int rssi)
{
	if(!p) {
		return;
	}

	p->rssi = rssi;

	return;
}

void mesh_stats_set_size(struct stats_entry *p, uint16_t size)
{
	if(!p) {
		return;
	}

	p->size = size;

	return;
}

void mesh_stats_set_msgdata(struct stats_entry *p, const uint8_t *data, uint16_t len)
{
	if(!p) {
		return;
	}

	p->msglen = len;

	p->msg = malloc(len);
	if(!p->msg) {
		return;
	}

	memcpy(p->msg, data, len);

	return;
}

void mesh_stats_set_ttl(struct stats_entry *p, int ttl)
{
	if(!p) {
		return;
	}

	p->ttl = ttl;

	return;
}

void mesh_stats_set_src(struct stats_entry *p, uint16_t src)
{
	if(!p) {
		return;
	}

	p->src = src;

	return;
}

void mesh_stats_set_dest(struct stats_entry *p, uint16_t dest)
{
	if(!p) {
		return;
	}

	p->dest = dest;

	return;
}

void mesh_stats_set_seqn(struct stats_entry *p, uint16_t seq)
{
	if(!p) {
		return;
	}

	p->seq = seq;

	return;
}

void mesh_stats_set_nkeyid(struct stats_entry *p, uint8_t nkeyid)
{
	if(!p) {
		return;
	}

	p->nkeyid = nkeyid;

	return;
}

void mesh_stats_set_opcode(struct stats_entry *p, uint8_t opcode)
{
	if(!p) {
		return;
	}

	p->opcode = opcode;

	return;
}

void mesh_stats_set_win_factor(struct stats_entry *p, uint8_t win_factor)
{
	if(!p) {
		return;
	}
	uint8_t winScale = (win_factor >> 3) & 3;
	p->win_factor = (frnd_relay_window * scalingFriend[winScale]) / 10;

	return;
}

void mesh_stats_set_prev_friend(struct stats_entry *p, uint16_t prev_friend)
{
	if(!p) {
		return;
	}

	p->prev_friend = prev_friend;

	return;
}

void mesh_stats_set_akeyid(struct stats_entry *p, uint8_t akeyid)
{
	if(!p) {
		return;
	}

	p->akeyid = akeyid;

	return;
}

void mesh_stats_set_hash(struct stats_entry *p, uint64_t hash)
{
	if(!p) {
		return;
	}

	p->hash = hash;

	struct stats_entry *e = first_entry;

	while(e != NULL) {
		if(e->hash == p->hash && p != e) {
			// Duplicate found
			p->properties |= STATS_DUPLICATE;
			p->duplicateof = e->id;
			break;
		}

		e = e->next;
	}
}

void mesh_stats_set_property(struct stats_entry *p, uint32_t prop)
{
	if(!p) {
		return;
	}

	p->properties |= prop;

	return;
}

// Build reply message for client. Contains only basic information on the packet because of packet size limit.
static uint16_t build_record_reply(uint16_t id, uint8_t *buf)
{
	int i;
	uint16_t n;

	//l_debug("stats: record %d requested.", id);

	n = mesh_model_opcode_set(OP_STATS_RECORD, buf);

	if(id >= num_records) {
		buf[n++] = RECORD_INVALID;

		return n;
	}

	struct stats_entry *record = first_entry;
	for(i = 0; i < id; i++) {
		record = record->next;
	}

	buf[n++] = RECORD_VALID;
	l_put_le32(record->timestamp, &buf[n]);
	n += 4;
	l_put_le16(record->id, &buf[n]);
	n += 2;
	buf[n++] = record->size;
	l_put_le32(record->properties, &buf[n]);
	n += 4;
	buf[n++] = record->ttl;
	l_put_le16(record->rssi, &buf[n]);
	n += 2;
	l_put_le16(record->duplicateof, &buf[n]);
	n += 2;
	l_put_le16(record->src, &buf[n]);
	n += 2;
	l_put_le16(record->dest, &buf[n]);
	n += 2;
	buf[n++] = record->opcode;	
	buf[n++] = record->win_factor;	
	l_put_le16(record->prev_friend, &buf[n]);
	n += 2;
	return n;
}

// Handle incoming packets
static bool stats_srv_pkt(uint16_t src, uint32_t dst,
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
	uint16_t n, id;
	bool send_state = false;

	if (mesh_model_opcode_get(pkt, size, &opcode, &n)) {
		size -= n;
		pkt += n;
	} else
		return false;

	hb = mesh_net_heartbeat_get(net);
	//l_debug("STATS-SRV-opcode 0x%x size %u idx %3.3x", opcode, size, idx);

	node = mesh_net_local_node_get(net);
	n = 0;

	switch (opcode) {
	default:
		return false;

	case OP_STATS_BEACON:
		// Beacon packets are ignored for now.
		break;

	case OP_STATS_GET_RECORD:
		// Send reply packet
		id = l_get_le16(pkt);
		n = build_record_reply(id, msg);
		break;

	case OP_STATS_GET_INFO:
		// Send number of records
		n = mesh_model_opcode_set(OP_STATS_INFO, msg);
		l_put_le16(num_records, msg + n);
		n += 2;
		break;

	}

	if (n) {
		/* print_packet("App Tx", long_msg ? long_msg : msg, n); */
		mesh_model_send(net, STATS_SRV_MODEL,
				unicast, src,
				idx, mesh_net_get_default_ttl(c_net),
				msg, n);
	}

	return true;
}

// Clean up model
static void statsmod_srv_unregister(void *user_data)
{
	struct mesh_net *net = user_data;
	struct mesh_net_heartbeat *hb = mesh_net_heartbeat_get(net);

	l_timeout_remove(hb->pub_timer);
	l_timeout_remove(hb->sub_timer);
	hb->pub_timer = hb->sub_timer = NULL;
}

// We need to know the appkey that is bound to the model to send data
static int statsmod_cli_bind(uint16_t app_idx, int action)
{
	//l_debug("stats: bind app_idx %d action %d", app_idx, action);

	bound_app_key = app_idx;

	return 0;
}

// Model callbacks
static const struct mesh_model_ops ops = {
	.unregister = statsmod_srv_unregister,
	.recv = stats_srv_pkt,
	.bind = statsmod_cli_bind,
	.sub = NULL,
	.pub = NULL
};

// Registers the model
void mesh_stats_srv_init(struct mesh_net *net, uint8_t ele_idx)
{
	//l_debug("%2.2x", ele_idx);
	mesh_model_vendor_register(net, ele_idx, STATS_SRV_MODEL, &ops, net);

	c_net = net;
}

// Tries to open the output file and writes header
int mesh_stats_srv_set_file(const char *file)
{
	ofile = fopen(file, "w");

	if(!ofile) {
		return -1;
	}

	//fprintf(ofile, "sent time, recv time, id, rssi, size, ttl, hash, duplicateof, src, dest, seq, nkeyid, akeyid, properties, msglen, msg\n");
	fprintf(ofile, "sent time, recv time, id, rssi, channel, size, ttl, hash, duplicateof, src, dest, opcode, win_factor, prev_friend, seq, nkeyid, akeyid, properties, msglen, msg\n");
	fflush(ofile);

	return 0;
}

// Sends a beacon message to dest with TTL ttl
void mesh_stats_srv_send_beacon(uint16_t dest, int ttl)
{
	uint16_t n;
	uint8_t msg[11];

	n = mesh_model_opcode_set(OP_STATS_BEACON, msg);

	struct mesh_node *node = mesh_net_local_node_get(c_net);

	mesh_model_send(c_net, STATS_SRV_MODEL,
					0, dest,
					bound_app_key, ttl,
					msg, n);
}
