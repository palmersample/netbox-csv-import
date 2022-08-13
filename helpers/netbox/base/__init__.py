# pylint: disable=use-tuple-over-list
"""
Define public imports for NetBox classes.
"""
from .base_classes import (Netbox,
                           NetboxBaseDevice,
                           NetboxImportError,
                           NetboxDataValidationError,
                           NetboxDeviceDataValidationError,
                           NetboxInterfaceDataValidationError,
                           NetboxDeviceImportError,
                           NetboxInterfaceImportError)

from .base_models import (NetboxBaseDeviceModel,
                          NetboxBaseInterfaceModel,
                          )

from .base_functions import (generate_import_dicts,
                             generate_custom_fields,
                             validate_device_dict,
                             validate_interface_dict)

__all__ = ["Netbox",
           "NetboxBaseDevice",
           "NetboxBaseDeviceModel",
           "NetboxBaseInterfaceModel",
           "NetboxImportError",
           "NetboxDataValidationError",
           "NetboxDeviceDataValidationError",
           "NetboxInterfaceDataValidationError",
           "NetboxDeviceImportError",
           "NetboxInterfaceImportError",
           "generate_import_dicts",
           "generate_custom_fields",
           "validate_device_dict",
           "validate_interface_dict"
           ]
