"""
pydantic classes and helper functions used for field validation.  Classes
defined in this file may be inherited by more device- or interface-specific
validation classes.

Baseline options and required fields should be defined in these models.

Note: at the time of creation, model fields are the minimum necessary to
support an initial use case for Wireless AP import.  Additional fields
will eventually be added to more accurately represent the expected NetBox
API payloads.
"""
# pylint: disable=too-few-public-methods, no-name-in-module, no-self-argument
from logging import getLogger
from typing import Optional, Union, Callable
from pydantic import BaseModel, validator, constr, root_validator
from netaddr import valid_mac

logger = getLogger(__name__)


def check_mac_address(mac_address: str) -> str:
    """
    Validate that a field listed as a MAC address is actually valid, using the
    Python "netaddr" library.

    :param mac_address: MAC address to validate
    :raises:
        ValueError: if the tested MAC address is not valid
    :return: Validated MAC address on success
    """
    if not valid_mac(mac_address):
        raise ValueError(f"MAC Address not valid: {mac_address}")
    return mac_address


def check_device_status(status: str) -> str:
    """
    Validate that a provided device status meets the requirements of the
    NetBox field.

    :param status: Requested device status
    :raises:
        ValueError: if the tested status is not valid
    :return: Validated device status on success
    """
    permitted_status = ("active", "decommissioning", "failed",
                        "inventory", "offline", "planned", "staged")

    if not status.lower() in permitted_status:
        raise ValueError(f"Device status is invalid. "
                         f"Requested: {status}, permitted: {permitted_status}")
    return status.lower()


def string_validation_wrapper(validation_func: Callable, field: str) -> classmethod:
    """
    Wrapper function for string values.  Permits easier re-use of validators
    across different pydantic models.

    Invocation for a specific field in a model is:

    _field_name_validation: str = string_validation_wrapper(validation_function, "field_name")

    :param validation_func: Validation function to be wrapped and returned
    :param field: Field to validate against check_device_status()
    :return: Wrapped validation function (check_mac_address()
    """
    decorator = validator(field, allow_reuse=True)
    validation_result = decorator(validation_func)
    return validation_result


class NetboxBaseDeviceModel(BaseModel):
    """
    NetBox basic device model.  Extend as needed for snowflakes or devices
    with custom fields... otherwise, this should fit most cases.
    """
    id: Union[int, None]
    name: constr(min_length=1)
    serial: str
    asset_tag: Optional[str]
    device_role: str
    manufacturer: Optional[str]
    device_type: str
    region: Optional[str]
    site: str
    location: Optional[str]
    status: Optional[str] = "active"
    platform: Optional[str]

    # Validate the status if provided.  Default value is "active"
    _status_validation: classmethod = string_validation_wrapper(check_device_status,
                                                                "status")


class NetboxBaseInterfaceModel(BaseModel):
    """
    Base interface model.  Extend for custom device types such as wireless
    access points or when interfaces require custom fields.  Basic
    validation is performed.
    """
    id: Union[int, None]
    name: str
    mac_address: str
    enabled: Optional[bool] = True

    # Validate the mac address (mandatory field).
    _mac_address_validation: classmethod = string_validation_wrapper(check_mac_address,
                                                                     "mac_address")

    @root_validator(pre=True)
    def mac_to_mac_address(cls, values):
        """
        Given a dict input with field name "mac", set the resulting output
        "mac_address" field to the same value so a proper base interface
        is generated.

        :param values: Dict of all values passed to the pydantic Model class.
            If it was passed to the model, it should be contained in this dict
        :return: "values" dict with the mac_address key set to "mac"
            if present.
        """
        if mac_address := values.get("mac"):
            values["mac_address"] = mac_address
        return values
