"""
Docstring
"""
# pylint: disable=too-few-public-methods, no-self-argument, no-name-in-module
from logging import getLogger
from typing import Optional, Any
from pydantic import BaseModel, root_validator
from .wireless_vars import (allowed_channel_numbers_24ghz,
                            allowed_channel_numbers_5ghz,
                            netbox_channel_width_translation,
                            netbox_channel_to_cisco_wlc_translation,
                            channel_center_frequencies,
                            allowed_channel_width_5ghz,
                            default_channel_width_5ghz,
                            default_channel_width_24ghz)
from.base_models import NetboxBaseDeviceModel, NetboxBaseInterfaceModel

logger = getLogger(__name__)


class NetboxWirelessApDeviceCustomFields(BaseModel):
    """
    Model representing Wireless AP device custom fields from NetBox.
    """
    wlc_primary_association: Optional[int]
    wlc_secondary_association: Optional[int]
    wlc_tertiary_association: Optional[int]


class NetboxWirelessApDeviceModel(NetboxBaseDeviceModel):
    """
    Wireless access point device model.  Inherits from the base device
    model and adds custom fields for validation.
    """
    custom_fields: NetboxWirelessApDeviceCustomFields


class NetboxWirelessApInterfaceCustomFields(BaseModel):
    """
    Wireless access point custom field definitions.
    """
    wlc_rf_channel: Optional[str]


class NetboxWirelessApInterfaceModel(NetboxBaseInterfaceModel):
    """
    Wireless access point interface, inheriting from the base interface model.
    Adds wireless-relevant fields as well as the interface custom fields.

    Note that rf_channel_frequency should always return None.  This is to
    prevent an error during update of NetBox fields - if rf_channel has
    been set initially, the channel_width and channel_frequency will be set.
    If this happens, an error will be thrown when updating rf_channel UNLESS
    channel_width and channel_frequency are set to valid values.  To avoid this
    behavior, we are expecting a valid channel and width, but do not care about
    the center frequency... so just send a "None" to the API and let NetBox
    null the field out.
    """
    rf_role: Optional[str]
    tx_power: Optional[int]
    rf_channel_frequency: Any = None
    rf_channel_width: int
    rf_channel: Optional[str]
    custom_fields: NetboxWirelessApInterfaceCustomFields

    @root_validator(pre=True)
    def validate_channel(cls, values):
        """
        Run before model validation. Ensure the supplied channel meets
        eligibility based on the definitions from wireless variables.

        :param values: Dict of all values sent to pydantic for validation
        :raises:
            AssertionError: If the channel is not in the allowed channel list
                for either 2.4 or 5 GHz.
        :return: values with validated channel number, cast to int()
        """
        if rf_band := values.get("band"):
            if channel_number := values.get("channel_number"):
                channel_number = int(channel_number)
            else:
                raise ValueError("Channel number must be specified for radio interfaces")

            if rf_band == "2.4":
                assert channel_number in allowed_channel_numbers_24ghz, \
                    f"2.4GHz Channel number must be in {allowed_channel_numbers_24ghz}"

            elif rf_band == "5":
                assert channel_number in allowed_channel_numbers_5ghz, \
                    f"5GHz Channel number must be in {allowed_channel_numbers_5ghz}"

            values["channel_number"] = channel_number
        return values

    @root_validator(pre=True)
    def validate_channel_width(cls, values):
        """
        Run before model validation.  If the band is 2.4GHz, set the value
        for rf_channel_width to 22MHz (not many people care about this).

        If the band is 5GHz, check that the requested channel width is
        permitted as defined in the imported wireless variables.  If no
        channel width is supplied, set the resulting value to the default
        (again, as defined in the imported wireless vars)

        :param values: Dict of all values sent to pydantic for validation
        :raises:
            AssertionError: If 5GHz channel width is supplied and not within
                the permitted list of channel widths
        :return: values with validated channel width, cast to int()
        """
        if rf_band := values.get("band"):
            if rf_band == "2.4":
                values["rf_channel_width"] = default_channel_width_24ghz
            elif rf_band == "5":
                if channel_width := values.get("channel_width"):
                    channel_width = int(channel_width)

                    assert channel_width in allowed_channel_width_5ghz,\
                        f"Channel width must be in {allowed_channel_width_5ghz}"

                    values["rf_channel_width"] = channel_width
                else:
                    values["rf_channel_width"] = default_channel_width_5ghz

        return values

    @root_validator(pre=True)
    def set_rf_channel(cls, values):
        # pylint: disable=loop-invariant-statement
        """
        In some cases, there may be a disconnect between the 'true' channel
        number (as represented in NetBox) and what a wireless controller
        expects.

        For example, a Cisco WLC supports many channel widths, but
        the configured channel is the first channel in the bonded channels.
        Thus, if 20MHz channels 36 and 40 are used to create the 40MHz channel
        38, the Cisco WLC expects this channel to be defined at 36 with 40MHz
        width, but NetBox stores the channel and width as a concatenated string
        with a center frequency: 5g-38-5190-40.

        This validator uses dictionaries imported from the wireless vars to
        transform the band, channel number, and desired width into the expected
        NetBox channel value.

        A new key, "netbox_channel_nunmber," will be added to the values() dict
        before return for use during a reverse transformation validator.

        :param values: Dict of all values sent to pydantic for validation
        :return: values with validated rf_channel (str()) and a new key,
            "netbox_channel_number", for further validation and NetBox import
        """
        if rf_band := values.get("band"):
            if values["rf_channel_width"] in netbox_channel_width_translation:
                for channel_tuple, translated_channel in \
                        netbox_channel_width_translation[values["rf_channel_width"]].items():
                    if values["channel_number"] in channel_tuple:
                        netbox_channel_number = translated_channel
                        break
            else:
                netbox_channel_number = values["channel_number"]

            values["rf_channel"] = f"{rf_band}g-{netbox_channel_number}-" \
                                   f"{int(channel_center_frequencies[netbox_channel_number])}" \
                                   f"-{values['rf_channel_width']}"

            values["netbox_channel_number"] = netbox_channel_number

        return values

    @root_validator(pre=True)
    def set_custom_field_rf_channel(cls, values):
        # pylint: disable=loop-invariant-statement, line-too-long
        """
        Reverse transformation from the NetBox RF channel number that was
        previously transformed from data and stored in the values() dict with
        key "netbox_channel_number".

        If the netbox channel number is found in the reverse transformation
        dict imported from the wireless vars, find the expected WLC channel
        number and set the custom field value.  This will permit proper
        device configuration with automated tasks, if necessary.

        :param values: Dict of all values sent to pydantic for validation
        :return: values with validated custom field "wlc_rf_channel"
        """
        if values.get("band") == "2.4":
            wlc_channel = values["channel_number"]
        elif values.get("band") == "5":
            if values["netbox_channel_number"] in netbox_channel_to_cisco_wlc_translation:
                wlc_channel = netbox_channel_to_cisco_wlc_translation[values["netbox_channel_number"]]
            else:
                wlc_channel = values["netbox_channel_number"]

        values["custom_fields"]["wlc_rf_channel"] = str(wlc_channel)

        return values
