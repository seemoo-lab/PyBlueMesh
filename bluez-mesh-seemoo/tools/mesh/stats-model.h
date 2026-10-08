// Vendor and model ID
#define STATS_VENDOR_ID	0xE00000
#define STATS_SRV_MODEL	(STATS_VENDOR_ID | 0xD0F0)
#define STATS_CLI_MODEL	(STATS_VENDOR_ID | 0xD0F1)

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


// Initializes the model and registers the submenu for the command line interface.
bool stats_client_init(uint8_t ele);
