
// Model IDs. Assigned by Bluetooth Mesh specification
#define ONOFF_SRV_MODEL	(VENDOR_ID_MASK | 0x1000)
#define ONOFF_CLI_MODEL	(VENDOR_ID_MASK | 0x1001)

// Supported opcodes
#define OP_ONOFF_GET                0x8201
#define OP_ONOFF_SET                0x8202
#define OP_ONOFF_SET_NOACK          0x8203
#define OP_ONOFF_STATUS             0x8204


// Initialize and register server model
void mesh_onoff_srv_init(struct mesh_net *net, uint8_t ele_idx);

// Set output file
int mesh_onoff_srv_set_file(const char *file);


// Initialize and register client model
void mesh_onoff_cli_init(struct mesh_net *net, uint8_t ele_idx);

// Send onoff message to address with state set to enable
void mesh_onoff_cli_set(int address, int enable);
