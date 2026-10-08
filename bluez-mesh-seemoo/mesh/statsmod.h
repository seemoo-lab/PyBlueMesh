
// Define vendor and model ID. Chosen arbitrarily.
#define STATS_VENDOR_ID	0x00E00000
#define STATS_SRV_MODEL	(STATS_VENDOR_ID | 0xD0F0)

// All supported opcodes
#define OP_STATS_GET_RECORD         (STATS_VENDOR_ID | 1)
#define OP_STATS_GET_INFO           (STATS_VENDOR_ID | 2)
#define OP_STATS_RECORD             (STATS_VENDOR_ID | 3)
#define OP_STATS_INFO               (STATS_VENDOR_ID | 4)
#define OP_STATS_BEACON             (STATS_VENDOR_ID | 5)

// Whether a record is valid or not. Used in replies to client.
#define RECORD_VALID   0x00
#define RECORD_INVALID 0xff

// All properties
#define STATS_DUPLICATE    (1 << 0) // Packet is duplicate
#define STATS_NOKEY        (1 << 1) // No net key found for decryption
#define STATS_PARSEERR     (1 << 2) // Error while parsing packet
#define STATS_OWN          (1 << 3) // Packet was sent by us
#define STATS_RELAYED      (1 << 4) // We relayed the packet


// Initializes and registers the model
void mesh_stats_srv_init(struct mesh_net *net, uint8_t ele_idx);

// Sets output file name
int mesh_stats_srv_set_file(const char *file);

// Send a beacon to dest with TTL ttl
void mesh_stats_srv_send_beacon(uint16_t dest, int ttl);

// Start and finish handling of a packet
struct stats_entry *mesh_stats_add_packet(void);
void mesh_stats_finish_packet(struct stats_entry *p);

// Functions for setting properties
void mesh_stats_set_timestamp(struct stats_entry *p, uint32_t timestamp);
void mesh_stats_set_chan(struct stats_entry *p, uint8_t chan);
void mesh_stats_set_rssi(struct stats_entry *p, int rssi);
void mesh_stats_set_size(struct stats_entry *p, uint16_t size);
void mesh_stats_set_msgdata(struct stats_entry *p, const uint8_t *data, uint16_t len);
void mesh_stats_set_property(struct stats_entry *p, uint32_t prop);
void mesh_stats_set_ttl(struct stats_entry *p, int ttl);
void mesh_stats_set_src(struct stats_entry *p, uint16_t src);
void mesh_stats_set_dest(struct stats_entry *p, uint16_t dest);
void mesh_stats_set_opcode(struct stats_entry *p, uint8_t opcode);
void mesh_stats_set_win_factor(struct stats_entry *p, uint8_t win_factor);
void mesh_stats_set_prev_friend(struct stats_entry *p, uint16_t prev_friend);
void mesh_stats_set_seqn(struct stats_entry *p, uint16_t seq);
void mesh_stats_set_nkeyid(struct stats_entry *p, uint8_t nkeyid);
void mesh_stats_set_akeyid(struct stats_entry *p, uint8_t akeyid);
void mesh_stats_set_hash(struct stats_entry *p, uint64_t hash);
