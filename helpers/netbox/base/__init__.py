# pylint: disable=use-tuple-over-list
"""
Define public imports for NetBox classes.
"""
from .base_classes import (Netbox,
                           NetboxBaseDevice)

from .base_models import (NetboxBaseDeviceModel,
                          NetboxBaseInterfaceModel)

from .base_functions import (generate_import_dicts,
                             generate_custom_fields,
                             validate_device_dict,
                             validate_interface_dict)

__all__ = ["Netbox",
           "NetboxBaseDevice",
           "NetboxBaseDeviceModel",
           "NetboxBaseInterfaceModel",
           "generate_import_dicts",
           "generate_custom_fields",
           "validate_device_dict",
           "validate_interface_dict"
           ]
