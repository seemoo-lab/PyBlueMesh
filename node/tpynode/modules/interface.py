import logging

from tpynode import TPyModule

logger = logging.getLogger(__name__)


class Interface(TPyModule):

    def __init__(self, **kwargs):
        self._interface = kwargs.get('interface', None)
        super(Interface, self).__init__(**kwargs)
