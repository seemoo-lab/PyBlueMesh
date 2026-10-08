import Pyro4
from .wigigwmi import WiGigWMI
from .rfantenna import RFAntenna


class WiGigIface (WiGigWMI, RFAntenna):

    """WiGigIface Module.
    Provides control over an Wireless IEEE 802.11ad Interface.
    """

    def __init__(self, **kwargs):
        super(WiGigIface, self).__init__(**kwargs)

    @Pyro4.expose
    def select_enabled_tx_sectors(self, sectors, cid):
        order = sectors + ([0xff] * (128 - len(sectors)))
        n = len(sectors)
        if self.wmi_prio_tx_sectors_order(order, 0x02, cid):
            raise Exception('Error setting sector order')
        if self.wmi_prio_tx_sectors_number(n, n, cid):
            raise Exception('Error setting sector number')
