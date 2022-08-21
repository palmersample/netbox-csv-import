"""
Exceptions to be raised by NetBox import classes
"""


class NetboxImportError(Exception):
    """
    Base Exception class - catching this will catch other exceptions raised
    during the CSV import process.
    """


class NetboxDeviceDataValidationError(NetboxImportError):
    """
    Exception class to be raised if there is an error validating the device
    information against the corresponding pydantic model.
    """


class NetboxInterfaceDataValidationError(NetboxImportError):
    """
    Exception class to be raised if there is an error validating the interface
    information against the corresponding pydantic model.
    """


class NetboxDeviceImportError(NetboxImportError):
    """
    Exception class to be raised if there is an error creating or updating the
    device in NetBox.
    """


class NetboxSkipImport(NetboxImportError):
    """
    Generic flow control class to be raised if an import should be skipped -
    for example, all data is valid but the "no update" flag has been passed,
    so an existing device should not be imported.
    """

class NetboxInterfaceImportError(NetboxImportError):
    """
    Exception class to be raised if there is an error updating interface(s)
    associated with a device in NetBox.
    """


class NetboxDataValidationError(NetboxImportError):
    """
    Generic data validation error to be raised. Simplifies exception catching
    in calling functions / scripts - while a specific exception may be caught
    during the import process, the DataValidationError will be raised with a
    useful message to indicate that the current row can't be imported.
    """
