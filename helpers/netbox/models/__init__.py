# pylint: disable=use-tuple-over-list
"""
Define public imports for NetBox data validation models.
"""
from .base_models import (NetboxBaseDeviceModel,
                          NetboxBaseInterfaceModel)

from .wireless_models import (NetboxWirelessApDeviceModel,
                              NetboxWirelessApInterfaceModel)

__all__ = ["NetboxBaseDeviceModel",
           "NetboxBaseInterfaceModel",
           "NetboxWirelessApDeviceModel",
           "NetboxWirelessApInterfaceModel"]
