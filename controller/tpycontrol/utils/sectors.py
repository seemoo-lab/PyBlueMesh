import copy
import logging
import numpy as np
from tabulate import tabulate

default_zero_sector_definition = {
    'dtype': [0] * 8,
    'etype': [0] * 32,
    'psh': [0] * 32,
    'x16': 48
}

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def print_sector_codebook(device):
    codebook = device.wil6210iface.get_rf_tx_sector_codebook()
    print(tabulate(codebook, headers='keys'))
