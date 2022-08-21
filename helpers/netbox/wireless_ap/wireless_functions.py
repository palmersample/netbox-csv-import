"""
Functions used by Wireless Access Point CSV import. CSV import to a new AP
in the main script should use the access_point function to instantiate the
proper class and initialize attributes for each device to add or update.

NOTE: this file has been heavily commented to facilitate learning opportunities

NOTE: I am not 100% satisfied with the number of imports and called functions.
      There is improvement potential here, but time dictates moving on to other
      tasks :)
"""
from logging import getLogger
from re import compile as re_compile
from requests.exceptions import ConnectionError as RequestsConnectionError
from pynetbox.core.query import RequestError as NetboxRequestError
from ..exceptions import (NetboxDeviceDataValidationError,
                          NetboxInterfaceDataValidationError,
                          NetboxDeviceImportError,
                          NetboxInterfaceImportError)
from .wireless_classes import NetboxWirelessAp
from ..base import (generate_import_dicts,
                    generate_custom_fields,
                    validate_device_dict,
                    validate_interface_dict)
from .wireless_models import (NetboxWirelessApDeviceModel,
                              NetboxBaseInterfaceModel,
                              NetboxWirelessApInterfaceModel)

logger = getLogger(__name__)

#############################################################################
# BEGIN common variables for functions in this script
#

# Compile the regular expression to identify interfaces from the CSV row
# headers.  Anything here will be passed to generate_import_dicts so
# interface-specific fields are identified.
interface_regex = re_compile(r"^(wired|radio\d+)_(.*)$")

# Define the pydantic model classes to be used for the device and interface
# dictionaries.
# pylint: disable-next=invalid-name
device_validation_class = NetboxWirelessApDeviceModel

# Custom field mapping for devices - field name is the key, str representation
# of a NetBox class method as the value. If the method exists and is callable,
# it will be used to populate the custom field.
device_custom_field_map = {
    "wlc_primary_association": "get_device_id",
    "wlc_secondary_association": "get_device_id",
    "wlc_tertiary_association": "get_device_id",
}

# Define validation models for different interface types.  Wired interfaces
# don't have some of the wireless fields (Tx power, channel width, etc.)
interface_to_validator_class_map = {
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

#
# END common variables for functions in this script
#############################################################################


def access_point(netbox_url,
                 netbox_token,
                 csv_row,
                 update_mode=True,
                 tls_verify=True,
                 msg_queue=None,
                 log_configurer=None):
    # pylint: disable=too-many-locals, too-many-arguments, line-too-long, loop-global-usage
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
    :param update_mode: Boolean - whether to update or skip existing devices
    :param tls_verify: Boolean - Enable/Disable TLS cert chain validation
    :param msg_queue: Multiprocessing message queue. If defined along with the
        log_configurer, logging will be configured to send to a root logging
        process via the provided MP message queue.
    :param log_configurer: Optional function passed by multiprocessing.Process
        which is used to configure logging to the root logger process.
    :return: None
    """
    try:

        #########################################################################
        # Step 1: If multiprocessing is used, configure the logger to use the
        #         message queue via the passed log_configurer function.
        #
        if msg_queue and log_configurer:
            try:
                log_configurer(msg_queue)
            except TypeError as err:
                logger.error("Unable call log configuration function. "
                             "Verify in the calling script and try again.\n\t"
                             "Details: %s", err)

        #####################################################################
        # Step 2: Generate the device and interfact dicts from the CSV row
        #
        device_dict, interface_dict = generate_import_dicts(interface_regex, csv_row)

        #####################################################################
        # Step 3: Generate device and interface custom fields, if needed
        #

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

        #####################################################################
        # Step 4: Validate the device and interface dictionaries after
        #         custom fields have been added.
        #
        try:
            # Validate the device and interface dictionaries
            valid_device = validate_device_dict(validator_class=device_validation_class,
                                                device_dict=device_dict)

            valid_interfaces = validate_interface_dict(interface_dict=interface_dict,
                                                       interface_validation_map=interface_to_validator_class_map)


            #################################################################
            # Step 5: Instantiate a NetboxWirelessAp object and call the
            #         netbox_import() method to build the device
            #

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


        #####################################################################
        # FINAL STEPS: Catch exceptions from data validation and the import
        #              process.

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
