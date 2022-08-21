"""
Common helper functions for NetBox import tasks. Any function here may be
imported and used in other function helper scripts to assist with data
validation or retrieval from the base ecosystem.
"""
from copy import copy as dict_copy
from logging import getLogger
from re import match as re_match
from pydantic import ValidationError
from ..exceptions import (NetboxDataValidationError,
                          NetboxDeviceDataValidationError,
                          NetboxInterfaceDataValidationError)
from .base_classes import Netbox
logger = getLogger(__name__)


def generate_import_dicts(interface_regex, csv_row):
    # pylint: disable=loop-invariant-statement
    """
    Process the current CSV row and split into two dicts: one containing
    device data and another containing interface definitions.

    Interface prefixes are identified by the interface_regex argument and
    each matching interface field becomes a new key in the interface dict.

    Returned interface_dict is nested, where the first key is the interface
    name and the value is a dict of all attributes associated with that
    interface.  Any CSV field header that is associated with an interface
    is popped off of the device_dict (which starts as a copy of the CSV
    row).

    Returned device_dict is simple - key/value pairs that are not identified
    as being associated with an interface and have survived the pop process.

    :param interface_regex: Compiled regular expression that identifies
        column headers associated with an interface - for example,
        radio0_tx_power will be added to interface "radio0" as key "tx_power"
    :param csv_row: Current CSV row being processed
    :return: Tuple containing the device_dict and interface_dict
    """
    device_dict = dict_copy(csv_row)
    interface_dict = {}

    for header, value in csv_row.items():
        if interface_data := re_match(interface_regex, header):
            (
                interface_name,
                interface_attribute,
            ) = interface_data.groups()

            if not interface_dict.get(interface_name):
                interface_dict.update(
                    {interface_name: {"name": interface_name}}
                )
            if value:
                interface_dict[interface_name].update(
                    {interface_attribute: value}
                )
            device_dict.pop(header)

    return device_dict, interface_dict


def get_interface_validation_model(model_map, interface_name):
    """
    Given a dict containing keys of interface base names (e.g. wired, radio)
    and values containing pydantic model class names, identify the
    desired validation class.

    :param model_map: Dict containing interface to model mapping
    :param interface_name: Name of the interface requiring a validation model
    :return: Name of pydantic model if found, None otherwise
    """
    interface_validation_class = None

    if model_map and interface_name:
        for interface_base_name, validation_class in model_map.items():
            if interface_base_name in interface_name:
                interface_validation_class = validation_class
                break

    return interface_validation_class


def validate_data(validation_class, unvalidated_dict):
    """
    Generic pydantic validation function.  Given a pydantic class
    and a dictionary, check for a pydantic ValidationError.

    :param validation_class: pydantic BaseModel class used for data validation
    :param unvalidated_dict: Dict to validate against the pydantic model
    :raises:
        NetboxDataValidationError: If pydantic raises a ValidationError
    :return: Validated dictionary on success
    """
    try:
        normalized_data = validation_class(**unvalidated_dict)
    except ValidationError as err:
        raise NetboxDataValidationError(err) from err
    else:
        validation_result = normalized_data.dict()
    return validation_result


def validate_device_dict(validator_class, device_dict):
    """
    Wrapper function for validate_data() to validate a device dict

    :param validator_class: pydantic class for device validation
    :param device_dict: Device dict to be validated
    :raises:
        NetboxDeviceDataValidationError: If NetboxDataValidationError is caught
            from validate_data()
    :return: Validated device dict on success
    """
    try:
        validated_device_data = validate_data(validator_class, device_dict)
    except NetboxDataValidationError as err:
        raise NetboxDeviceDataValidationError(err) from err
    return validated_device_data


def validate_interface_dict(interface_dict,
                            validator_class=None,
                            interface_validation_map=None):
    """
    Wrapper function for validate_data() to validate an interface dict

    :param interface_dict: Interface dict to validate.
    :param validator_class: pydantic class for interface validation.  If not
        specified, check for interface_validation_map.  If neither are
        specified, raise a NetboxInterfaceDataValidationError
    :param interface_validation_map: Mapping of interface names to validation
        class.  NOTE that this takes priority over the validator_class
        parameter.
    :raises:
        NetboxInterfaceDataValidationError: If NetboxDataValidationError is
            caught from validate_data() OR if no validation class or mapping
            is supplied.
    :return: Validated interface dict on success
    """
    validated_interface_data = {}

    if validator_class or interface_validation_map:
        try:
            for interface_name, interface_data in interface_dict.items():
                validation_class = get_interface_validation_model(interface_validation_map,
                                                                  interface_name) or validator_class
                validated_interface_dict = validate_data(validation_class, interface_data)
                validated_interface_data.update({interface_name: validated_interface_dict})
        except NetboxDataValidationError as err:
            raise NetboxInterfaceDataValidationError(f"Interface {interface_name}: {err}") from err
    else:
        raise NetboxInterfaceDataValidationError("Unable to validate interfaces, "
                                                 "no validation class or mapping dict provided.")

    return validated_interface_data


def generate_custom_fields(netbox_url, netbox_token, dict_data, custom_field_map, tls_verify):
    # pylint: disable=loop-try-except-usage
    """
    Given a dictionary of device or interface attributes and a mapping of
    custom fields to lookup generators, create a dictionary of NetBox
    custom field attributes to be added to the device/interface dictionary.

    Typically this will be called before model validation to ensure the
    complete API-ready dict conforms with NetBox's expectations.

    The custom_field_map is a dict with each key representing the expected
    custom field name and an optional method name to invoke from the Netbox
    base class.  If the method exists and is callable, it will be used to
    generate the custom field value.  If the value associated with the custom
    field name in the dict is None, it will be the resulting custom field
    dict value.

    :param netbox_url: Full URL to the NetBox instance
    :param netbox_token: API token for the NetBox instance
    :param dict_data: Device or interface data dict which is used to obtain
        the value used during custom field value generation.
    :param custom_field_map: Dict where each key is the name of a custom field
        and the value is either a Netbox class method name or None, indicating
        the custom field value will be the same as the value in dict_data.
    :return: Generated dict of custom field key/value pairs.
    """
    custom_fields = {}
    with Netbox(netbox_url=netbox_url,
                netbox_token=netbox_token,
                tls_verify=tls_verify) as netbox:
        for field_name, field_generator in custom_field_map.items():
            if field_value := dict_data.get(field_name):
                if hasattr(netbox, field_generator) and \
                        callable(func := getattr(netbox, field_generator)):
                    custom_fields.update({field_name: func(field_value)})
                else:
                    custom_fields.update({field_name: field_value})

                try:
                    dict_data.pop(field_name)
                except KeyError:
                    # If there is no matching field in the source dict, ignore
                    # the error and keep processing
                    pass
        return custom_fields
