"""
Base NetBox classes and associated helper functions.  Most of the definitions
here will be inherited by the appropriate device type imported (for example,
WirelessAccessPoint, WirelessLanController, or similar).

Functions not directly used by class definitions in this file should be places
in an appropriate file in helpers.netbox.functions.
"""
from json import dumps as json_dumps
from logging import getLogger
from requests import Session as requests_session
from pynetbox import api as netbox_api, RequestError as NetboxRequestError
from urllib3 import disable_warnings


logger = getLogger(__name__)


# Define the key fields for 'standard' devices and interfaces.  Any field not
# listed in these tuples will be assumed to require the "slug" option to be
# defined in the API payload.
device_key_fields = ("id", "name", "serial", "asset_tag", "status", "custom_fields")
interface_key_fields = ("id", "name", "mac_address", "enabled", "custom_fields")


def generate_api_dict(dict_data, key_fields=None):
    """
    This function is called from the NetBox base class(es) to generate an API
    payload using either the key fields or, when necessary, "slug" keys to
    enable NetBox to accept data without performing an expensive lookup for
    each object ID.

    :param dict_data: Source dictionary to be compared against the key fields.
        Any dict key not listed in key_fields will be moved to a sub-dict and
        prefixed with "slug"
    :param key_fields: Tuple or List of key fields to compare keys in dict_data
        for determination of "slugificaton".  If not specified, the resulting
        payload representation will be identical to the input.
    :return: Dict containing a NetBox API payload representation of the source
        data.
    """
    if not key_fields:
        key_fields = ()

    api_dict = {}
    for device_field, device_value in dict_data.items():
        if device_field in key_fields:
            api_dict.update({device_field: device_value})
        else:
            api_dict.update({device_field: {"slug": device_value}})

    return api_dict


def set_object_attributes(object_ref, dict_data):
    """
    Given an object reference and a dictionary representing the data to be
    reflected in the object, set object attributes so each field is
    accessible as an object property.  If the value of a key is another
    dictionary, recurse until the base case (key/value pair) is reached.

    :param object_ref: Source object for which attributes will be set
    :param dict_data: Dictionary to process.  Each key/value pair will become
        an attribute of object_ref.
    :return: None
    """
    for key, value in dict_data.items():
        if isinstance(value, dict):
            setattr(object_ref,
                    key,
                    set_object_attributes(object_ref, value)
                    )
        else:
            setattr(object_ref, key, value)


class NetboxDeviceDataValidationError(Exception):
    """
    Exception class to be raised if there is an error validating the device
    information against the corresponding pydantic model.
    """


class NetboxInterfaceDataValidationError(Exception):
    """
    Exception class to be raised if there is an error validating the interface
    information against the corresponding pydantic model.
    """


class NetboxDeviceImportError(Exception):
    """
    Exception class to be raised if there is an error creating or updating the
    device in NetBox.
    """


class NetboxSkipImport(Exception):
    """
    Generic flow control class to be raised if an import should be skipped -
    for example, all data is valid but the "no update" flag has been passed,
    so an existing device should not be imported.
    """

class NetboxInterfaceImportError(Exception):
    """
    Exception class to be raised if there is an error updating interface(s)
    associated with a device in NetBox.
    """


class NetboxDataValidationError(Exception):
    """
    This is going away...
    """


class NetboxImportError(Exception):
    """
    Generic class that is also going away...
    """


class Netbox:
    """
    Base NetBox class.  Contains generic methods to perform object lookups
    for devices and interfaces, as well as any other globally-required task.
    """
    def __init__(self, netbox_url, netbox_token, tls_verify=True):
        """
        NetBox object initialization.

        :param netbox_url: Full URL to NetBox instance
        :param netbox_token: NetBox Token for API authentication
        :param tls_verify: Boolean - determine if TLS chain validation is
            performed when consuming the NetBox API.
        """

        if not tls_verify:
            disable_warnings()

        self.api = netbox_api(url=netbox_url, token=netbox_token)

        # pynetbox does not support TLS validation enable/disable functionality
        # but does accept an optional Session object.  Use this to specify
        # the TLS validation option and attach the Session object to the
        # pynetbox instance.
        api_session = requests_session()
        api_session.verify = tls_verify
        self.api.http_session = api_session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def get_device_by_name(self, device_name):
        """
        Search for a single device using the Netbox dcim.devices endpoint

        :param device_name: Name of the device to lookup
        :return: pynetbox result
        """
        return self.api.dcim.devices.get(name=device_name)

    def get_device_interface_by_name(self, device_name, interface_name):
        """
        Search for a single interface associated with "device_name" via the
        NetBox dcim.interfaces endpoint.

        :param device_name: Name of the device containing the interface
        :param interface_name: Interface name on the device to return
        :return: pynetbox search result
        """
        return self.api.dcim.interfaces.get(name=interface_name, device=device_name)

    def get_device_id(self, device_name):
        """
        Search for a single device and, if present, return the associated NetBox
        object ID.

        :param device_name: Name of the device to search
        :return: NetBox object ID of the device if found, None otherwise.
        """
        try:
            device_id = self.get_device_by_name(device_name=device_name).id
        except AttributeError:
            device_id = None
        return device_id

    def get_interface_id(self, device_name, interface_name):
        """
        Search for a single interface on a device.  If present, return the
        associated NetBox object ID.

        :param device_name: Name of the device containing the interface
        :param interface_name: Interface name on the device
        :return: NetBox objet ID of the interface if found, None otherwise
        """
        interface_id = None

        if device_name and interface_name:
            try:
                interface_id = self.get_device_interface_by_name(device_name, interface_name).id
            except AttributeError:
                pass
            except NetboxRequestError as err:
                raise NetboxImportError(f"Unable to get interface ID: {err}") from err

        return interface_id


class NetboxBaseDevice(Netbox):
    # pylint: disable=invalid-name, too-many-arguments
    """
    Generic base class representing a NetBox device.  Specific device types
    should inherit this class when being imported.
    """
    class InterfaceContainer:
        """
        Object container for device interfaces.  Each interface will have
        unique attributes inside the InterfaceContainer.
        """
        class InterfaceClass:
            """
            Device Interface class.  Each interface associated with a device
            is represented by an instance of InterfaceClass.
            """
            def __init__(self, device_object, interface_dict):
                """
                InterfaceClass initializer.

                :param device_object: Object reference from the parent device.
                    This is used to perform NetBox API calls and obtain details
                    such as the parent device ID for payload generation.
                :param interface_dict: Dictionary representing the definitions
                    for the current interface
                """
                self.name = str
                self.id = int
                set_object_attributes(self, interface_dict)
                self._dict = interface_dict
                self._device = device_object

            def __repr__(self):
                """
                Representation of the InterfaceClass instance.  This will
                displayed when device_object.interfaces.interface_name is
                accessed.

                :return: String representation of the interface definition
                    dict.
                """
                return str(self._dict)

            @property
            def dict(self):
                """
                Property to return the raw dictionary attributes used when
                generating the interface

                :return: Interface dict representation as stored in the _dict
                    attribute.
                """
                return self._dict

            @property
            def json(self):
                """
                Property to return the JSON representation of the current
                interface properties specified in the initialization dict.

                :return: JSON representation of self.dict
                """
                return json_dumps(self.dict)

            @property
            def netbox_api_payload(self):
                """
                Property representing the "slugified" payload to be used for
                NetBox API consumption.

                :return: Dict created from generate_api_dict
                """
                return generate_api_dict(self.dict)

            def set_id(self):
                """
                Update the "id" attribute of the interface instance.  This is
                typically called after a new device is created so subsequent
                interface updates succeed, as the interface instance will
                contain associated the NetBox object ID.

                Once the ID has been set, update the _dict attribute to also
                include the k/v "id" pair so calls to the json or
                netbox_api_paylaod properties reflect properly.

                :return: None
                """
                self.id = self._device.get_interface_id(device_name=self._device.name,
                                                        interface_name=self.name)
                self._dict["id"] = self.id

        def __init__(self, parent_obj, interface_dict):
            """
            InterfaceContainer initialization.  Generates a list of interface
            names as they are created, to be used for __repr__.  Set the
            _dict attribute to contain the list of interface dicts representing
            the raw data passed during interface creation.

            Each interface name will become a new attribute where the value is
            an instance of InterfaceClass.

            :param parent_obj: Object reference of the parent device.
            :param interface_dict: List of dicts containing validated interface
                definitions
            """
            self._names = []
            self._key_fields = interface_key_fields
            self._dict = interface_dict
            self._iter_index = int
            for interface_name, interface_data in interface_dict.items():
                setattr(self, interface_name, self.InterfaceClass(device_object=parent_obj,
                                                                  interface_dict=interface_data)
                        )
                self._names.append(interface_name)

        def __repr__(self):
            """
            Representation of the InterfaceContainer object. This will be
            displayed when device_object.interfaces is accessed.

            :return: string representation of a list of interface names
            """
            return str(list(self._dict.keys()))

        @property
        def dict(self):
            """
            Property to return the raw dictionary attributes used when
            generating the interfaces.

            :return: List generated by comprehension of the _dict attribute
                for each interface
            """
            return [getattr(self, self._names[x]).dict for x in range(len(self._names))]

        @property
        def json(self):
            """
            Property to return the JSON representation of all
            interface properties specified in the initialization dict.

            :return: JSON representation of self.dict
            """
            return json_dumps(self.dict)

        @property
        def netbox_api_payload(self):
            """
            Property representing the "slugified" payload to be used for
            NetBox API consumption.

            :return: List created from generate_api_dict for each interface
            """
            return [generate_api_dict(x, self._key_fields) for x in self.dict]

        def __iter__(self):
            """
            InterfaceContainer is not iterable as it is designed to house
            InterfaceClass objects for each device interface.  This method
            returns an instance of the current interface object as generated
            by the __next__ method.

            The _iter_index attribute is set to 0 here so that each time an
            iterator is requested, the index is reset to 0 - otherwise only a
            single iteration would be possible to each caller.

            :return: self (instance of the current interface iteration)
            """
            self._iter_index = 0
            return self

        def __next__(self):
            """
            Iterate through each interface.  This is used in conjunction with
            the __iter__ method.

            When an iteration is requested - for example:

                "for interface in device.interfaces:"

            This method begins at self._iter_index (set to 0 in the __iter__
            method) and loops through each interface object, returning the
            next interface in the list to __iter__ for use by the caller.

            Once len(self._names), the list representation of all interfaces,
            is reached then a StopIteration is raised which indicates that the
            last item has been returned and the "for" loop terminates.

            :return: Next InterfaceClass instance in the list of interfaces. If
                no more instances are available, raise StopIteration.
            """
            if self._iter_index < len(self._names):
                lookup_field = self._names[self._iter_index]
                result_data = getattr(self, lookup_field)
            else:
                raise StopIteration
            self._iter_index += 1
            return result_data

    def __init__(self,
                 netbox_url,
                 netbox_token,
                 device_dict,
                 interface_dict,
                 update_mode=True,
                 tls_verify=True):  # ,
                 # **kwargs):
        self.name = str
        self.id = int
        self.update_mode = update_mode

        super().__init__(netbox_url=netbox_url, netbox_token=netbox_token, tls_verify=tls_verify)

        self._dict = device_dict
        set_object_attributes(self, device_dict)
        self._set_id()

        self.interfaces = self.InterfaceContainer(parent_obj=self, interface_dict=interface_dict)
        self._key_fields = device_key_fields

    def __repr__(self):
        """
        Representation of the NetboxBaseDevice object. This will be
        displayed when device_object is accessed.

        :return: string representation of the device name
        """
        return str(self.name)

    @property
    def dict(self):
        """
        Property to return the raw dictionary attributes used when
        generating the device.

        :return: Device dict representation as stored in the _dict
            attribute.
        """
        return self._dict

    @property
    def json(self):
        """
        Property to return the JSON representation of the
        device properties returned by self.dict

        :return: JSON representation of self.dict
        """
        return json_dumps(self.dict)

    @property
    def netbox_api_payload(self):
        """
        Property representing the "slugified" payload to be used for
        NetBox API consumption.

        :return: List created from generate_api_dict for this device.
        """
        return generate_api_dict(dict_data=self.dict, key_fields=self._key_fields)

    def _set_id(self, device_id=None):
        """
        Set the "id" attribute of the current device.  Used during
        instantiation to determine if the device has an ID (already
        exists in NetBox) or after a new device has been created.

        If a device ID is found in NetBox, also update the _dict
        attribute for the current device so property access reflects the
        current/proper data.

        Important in either case so that interface IDs are set before
        attempting to update the interface data.

        :return: None
        """
        if device_id:
            self.id = device_id
        else:
            self.id = self.get_device_id(device_name=self.name)
        self._dict.update({"id": self.id})

    def _create_device(self):
        """
        Create a new device in NetBox.  If successful, call self._set_id to
        update the device ID attribute.

        :raises: NetboxDeviceImportError
        :return: None
        """
        try:
            nb_result = self.api.dcim.devices.create(self.netbox_api_payload)
        except NetboxRequestError as err:
            raise NetboxDeviceImportError(err) from err
        else:
            self._set_id(device_id=nb_result.id)

    def _update_device(self):
        """
        Update an existing device in NetBox.  No additional tasks required on
        success, as this method will only be called if device.id exists.

        :raises: NetboxDeviceImportError
        :return: None
        """
        try:
            self.api.dcim.devices.update([self.netbox_api_payload])
        except NetboxRequestError as err:
            raise NetboxDeviceImportError(err) from err

    def _update_interfaces(self):
        """
        Updates interfaces associated with the current device.  Note that new
        devices are created from device types in NetBox (i.e. templates), so
        new devices will immediately have the interface templates assigned.

        Thus, new interface creation is not necessary for this use case, but
        attributes of the new device's interfaces must be set.

        This method invokes the dcim.interfaces.update method from pynetbox and
        passed the list of ALL interfaces as the payload in a single pass to
        reduce the expense incurred by TLS negotiation if a loop were used.

        :raises: NetboxInterfaceImportError
        :return: None
        """
        try:
            self.api.dcim.interfaces.update(self.interfaces.netbox_api_payload)
        except NetboxRequestError as err:
            raise NetboxInterfaceImportError(err) from err
        except TypeError as err:
            raise NetboxInterfaceImportError(err) from err

    def netbox_import(self):
        """
        Main import method.  When invoked, determine if an update is necessary
        for an existing device (update_mode is True and self.id is not None) or
        if a new device should be created.

        If update_mode is not True and a device ID exists, skip processing by
        raising NetboxSkipImport and creating a useful log message.

        Otherwise, create the device.  If successful, update all interfaces
        to include the 'id' attribute so each interface can be updated.

        :raises:
            NetboxSkipImport: (caught in this method) if device exists and
                update_mode is False.
            NetboxDeviceImportError: if the device import / update task
                fails
            NetboxInterfaceImportError: if the interface update task fails
        :return: None
        """
        def update_interface_ids():
            """
            Docstring.
            :param device_name:
            :return:
            """
            for interface in self.interfaces:
                interface.set_id()

        try:
            if self.id and self.update_mode:
                self._update_device()
            elif self.id and not self.update_mode:
                raise NetboxSkipImport
            else:
                self._create_device()
            update_interface_ids()

            self._update_interfaces()

        except NetboxSkipImport:
            logger.info("Device '%s' already exists and updates have been disabled."
                        " Skipping...", self.name)
        except NetboxDeviceImportError as err_msg:  # Catch pynetbox API errors
            raise NetboxDeviceImportError(f"Device '{self.name}' was not imported:"
                                          f"{err_msg}") from err_msg
        except NetboxInterfaceImportError as err_msg:
            raise NetboxInterfaceImportError(f"Device '{self.name}' was imported successfully "
                                             f"but interfaces were not configured. Details:\n"
                                             f"{err_msg}") from err_msg
        else:
            logger.info("Successfully imported device '%s' with interfaces %s",
                        self.name,
                        self.interfaces)
