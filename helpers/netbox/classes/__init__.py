# pylint: disable=use-tuple-over-list
"""
Define public imports for NetBox classes.
"""
from .netbox_base import (Netbox,
                          NetboxBaseDevice,
                          NetboxImportError,
                          NetboxDataValidationError,
                          NetboxDeviceDataValidationError,
                          NetboxInterfaceDataValidationError,
                          NetboxDeviceImportError,
                          NetboxInterfaceImportError)

from .netbox_wireless import NetboxWirelessAp

__all__ = ["Netbox",
           "NetboxImportError",
           "NetboxDataValidationError",
           "NetboxDeviceDataValidationError",
           "NetboxInterfaceDataValidationError",
           "NetboxDeviceImportError",
           "NetboxInterfaceImportError",
           "NetboxWirelessAp"]
