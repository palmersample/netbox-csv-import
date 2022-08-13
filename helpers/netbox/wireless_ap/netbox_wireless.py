"""
Class definitions for NetBox wireless devices (AP, WLC, etc).  Classes
defined here should inherit from base classes in base_classes.py.
"""
from logging import getLogger
from ..base import NetboxBaseDevice


logger = getLogger(__name__)

# Define the key fields for Wireless AP devices and interfaces.  Any field not
# listed in these tuples will be assumed to require the "slug" option to be
# defined in the API payload.
device_key_fields = ("id", "name", "serial", "asset_tag", "status", "custom_fields")
interface_key_fields = ("id", "name", "mac_address", "enabled", "rf_role",
                        "tx_power", "rf_channel", "custom_fields",
                        "rf_channel_frequency", "rf_channel_width")


class NetboxWirelessAp(NetboxBaseDevice):
    # pylint: disable=too-many-arguments
    """
    Class representing Wireless AP in NetBox for import.  Attributes are
    set during the super() call to the NetboxBaseDevice class.
    """
    def __init__(self,
                 netbox_url,
                 netbox_token,
                 device_dict,
                 interface_dict,
                 update_mode=True,
                 tls_verify=True):
        """
        Very simple initialization.  Call super() to generate attributes and
        override key fields for the device and interfaces to ensure proper API
        payload generation.

        :param netbox_url: Full URL of the NetBox instance
        :param netbox_token: API token to use for consuming NetBox resources
        :param device_dict: Validated dictionary of device attributes
        :param interface_dict: Validated dictionary of interface attributes
        :param tls_verify: Boolean - specify if TLS chain validation should be
            performed
        """

        super().__init__(netbox_url=netbox_url,
                         netbox_token=netbox_token,
                         device_dict=device_dict,
                         interface_dict=interface_dict,
                         update_mode=update_mode,
                         tls_verify=tls_verify)
        self.interfaces._key_fields = interface_key_fields
        self._key_fields = device_key_fields
