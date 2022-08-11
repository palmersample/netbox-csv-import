"""
Docstring.
"""
from logging import getLogger
from re import compile as re_compile
from requests.exceptions import ConnectionError as RequestsConnectionError
from pynetbox.core.query import RequestError as NetboxRequestError
from .base_functions import (generate_import_dicts,
                             generate_custom_fields,
                             validate_device_dict,
                             validate_interface_dict)
from ..classes import (NetboxWirelessAp,
                       NetboxDeviceDataValidationError,
                       NetboxInterfaceDataValidationError,
                       NetboxDeviceImportError,
                       NetboxInterfaceImportError)
from ..models import (NetboxWirelessApDeviceModel,
                      NetboxBaseInterfaceModel,
                      NetboxWirelessApInterfaceModel)

logger = getLogger(__name__)

# Define the pydantic model classes to be used for the device and interface
# dictionaries.
# pylint: disable-next=invalid-name
device_validation_class = NetboxWirelessApDeviceModel

# If there was no interface mapping dict created, define a static interface
# validation model name here.
# pylint: disable-next=invalid-name
# interface_validation_class = NetboxWirelessApInterfaceModel


def access_point(netbox_url,
                 netbox_token,
                 csv_row,
                 update_mode=True,
                 tls_verify=True,
                 msg_queue=None,
                 log_configurer=None):
    # pylint: disable=too-many-locals, too-many-arguments, line-too-long
    """
    Import a wireless access point.
      - Generate the device and interface dicts from the current CSV row.
      - Generate device and interface custom fields, update the corresponding
        dicts with the custom field data
      - Validate the device and interface dictionaries against the appropriate
        pydantic models
      - Instantiate the NetboxWirelessApDeviceModel with the device and
        interface dicts.  Call the netbox_import() method and catch any thrown
        exceptions.
      - For any exceptions, generate a meaningful logger.error message.

    :param netbox_url: Full URL of the NetBox instance
    :param netbox_token: API token used for interacting with NetBox
    :param csv_row: Current CSV row for import
    :return: None
    """
    try:
        if msg_queue and log_configurer:
            try:
                log_configurer(msg_queue)
            except TypeError as err:
                logger.error("Unable call log configuration function. "
                             "Verify in the calling script and try again.\n\t"
                             "Details: %s", err)

        # Compile the regular expression to identify interfaces from the CSV row
        # headers.  Anything here will be passed to generate_import_dicts so
        # interface-specific fields are identified.
        interface_regex = re_compile(r"^(wired|radio\d+)_(.*)$")

        device_custom_field_map = {
            "wlc_primary_association": "get_device_id",
            "wlc_secondary_association": "get_device_id",
            "wlc_tertiary_association": "get_device_id",
        }

        # Define validation models for different interface types.  Wired interfaces
        # don't have some of the wireless fields (Tx power, channel width, etc.)
        interface_to_validation_class_map = {
            "wired": NetboxBaseInterfaceModel,
            "radio": NetboxWirelessApInterfaceModel
        }

        # Note: interface custom fields are not used for the AP (wlc_rf_channel
        # is set via pydantic root validator).  This is inserted as an example
        # of setting interface custom fields that may use a NetBox lookup like
        # the device custom fields for an AP, but where the custom field lookup
        # results in the dict value being the same as the input value.
        interface_custom_field_map = {
            "wlc_rf_channel": None
        }

        # Generate the device and interfact dicts from the CSV row
        device_dict, interface_dict = generate_import_dicts(interface_regex, csv_row)

        # The device dictionary requires custom field lookups to determine the
        # primary, secondary, tertiary WLC object IDs.  Use generate_custom_fields
        # to pull this data from NetBox and add the custom fields to the device
        # dict.
        device_dict.update(
            {
                "custom_fields": generate_custom_fields(netbox_url=netbox_url,
                                                        netbox_token=netbox_token,
                                                        dict_data=device_dict,
                                                        custom_field_map=device_custom_field_map,
                                                        tls_verify=tls_verify)
            }
        )

        # Iterate over the interfaces and generate custom fields for each.  Note
        # that for the wireless AP, interface custom fields will be created as part
        # of the data validation process via pydantic root validators...
        for interface_data in interface_dict.values():
            interface_data.update(
                {
                    "custom_fields": generate_custom_fields(netbox_url=netbox_url,
                                                            netbox_token=netbox_token,
                                                            dict_data=interface_data,
                                                            custom_field_map=interface_custom_field_map,
                                                            tls_verify=tls_verify)
                }
            )

        try:
            # Validate the device and interface dictionaries
            valid_device = validate_device_dict(validator_class=device_validation_class,
                                                device_dict=device_dict)

            valid_interfaces = validate_interface_dict(interface_dict=interface_dict,
                                                       interface_validation_map=interface_to_validation_class_map)

            # Once the dicts have been validated, create a NetboxWirelessAp object
            # for each row and invoke the netbox_import method to create or update
            # the objects in NetBox.
            netbox = NetboxWirelessAp(netbox_url=netbox_url,
                                      netbox_token=netbox_token,
                                      device_dict=valid_device,
                                      interface_dict=valid_interfaces,
                                      update_mode=update_mode,
                                      tls_verify=tls_verify
                                      )
            netbox.netbox_import()

        # Catch any expected exceptions and generate appropriate log messages.
        # Successful import log message will be generated inside the netbox_import
        # method, assuming no exceptions are caught.
        except NetboxDeviceDataValidationError as err:
            logger.error("Device '%s': %s", csv_row.get("name"), err)
        except NetboxInterfaceDataValidationError as err:
            logger.error("Device '%s': %s", csv_row.get("name"), err)
        except NetboxDeviceImportError as err:
            logger.error(err)
        except NetboxInterfaceImportError as err:
            logger.error(err)

    except RequestsConnectionError as err:
        logger.error("Unable to connect to NetBox using provided URL. Check and re-try.")
        logger.debug("Error details: %s", err)
    except NetboxRequestError as err:
        logger.error("Unable to connect to NetBox using provided token. Check and re-try")
        logger.debug("Error details: %s", err)
    except AttributeError as err:
        logger.error("The provided CSV row does not appear to contain valid information.  Unable to process")
        logger.debug("Error details: %s", err)
    except OSError as err:
        logger.error("Unable to process the CSV row due to an unexpected OS error.\n\tDetails: %s", err)
