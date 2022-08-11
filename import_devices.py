"""
Main CSV import script.

Given a CSV file and device type (at minimum), read the CSV and leverage
multiprocessing to spawn a new process for each row which handles the
data formatting and calls to appropriate functions to create devices and
associated interface configuration in NetBox.
"""
import logging
from argparse import ArgumentParser
from csv import DictReader as CsvDictReader
from logging.handlers import QueueHandler as LoggingQueueHandler
from multiprocessing import (Queue as MpQueue,
                             Process as MpProcess,
                             Manager as MpManager)
from os import environ
from sys import (stdout as sys_stdout,
                 stderr as sys_stderr)
from traceback import print_exc
from time import time
from helpers import get_vault_secret, access_point, VaultError


# Initial logging configuration.  This logger will be used for any logs
# generated in this script.
logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler(sys_stdout)
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)

# Map device types (provided via argument) to the proper import function.
device_type_loader_mapping = {
    "access_point": access_point
}

# Location of NetBox secret inside HashiCorp Vault
VAULT_NETBOX_PATH = "infra/netbox"

# Grab the Vault URL and token from the environment. If not supplied, set
# generic defaults for a dev environment.
VAULT_URL = environ.get("VAULT_URL", "http://vault-dev")
VAULT_TOKEN = environ.get("VAULT_TOKEN", "developer_token")


def configure_root_logging():
    """
    This function is passed to the root logging process to initialize
    the logging targets, levels, formatting, etc.

    :return: None
    """
    root_logger = logging.getLogger()
    handler = logging.StreamHandler(sys_stdout)
    handler.setLevel(logging.INFO)
    root_formatter = logging.Formatter('%(asctime)s %(processName)-10s '
                                       '%(name)s %(levelname)-8s %(message)s')
    handler.setFormatter(root_formatter)
    root_logger.addHandler(handler)


def configure_worker_logging(msg_queue):
    """
    Each worker process is passed a reference to this function and will invoke
    to initialize the logger to send messages via the multiprocessing queue.
    This allows child loggers to send to the main (root) logging process
    without fear of locking issues.

    :param msg_queue: multiprocessing message queue used for log messages
    :return: None
    """
    log_handler = LoggingQueueHandler(msg_queue)
    worker_logger = logging.getLogger()
    worker_logger.addHandler(log_handler)
    worker_logger.setLevel(logging.DEBUG)


def root_logging_process(msg_queue, configurator):
    """
    This function is spawned into a separate process and acts as the root log
    listener.  Child processes send messages via logging.handler.QueueHandler
    through a multiprocessing message queue, which are then received by this
    logger.

    This implementation is based on the Python logging cookbook example for
    multiprocessing logging and is designed to provide a process-safe
    logger that can asynchronously write to a file (if desired) without
    locking issues.

    :param msg_queue: multiprocessing.Queue object to which this logger will
        attach and listen for incoming messages.
    :param configurator: Reference to the root log configuration function to
        be executed before listening for incoming messages.
    :return: None
    """
    # pylint: disable=loop-try-except-usage

    # Configure the root logger using the passed function reference
    configurator()

    # Not critical, added for performance to reduce load time of getLogger
    # inside the "while True" loop
    root_listener = logging.getLogger

    # Process the incoming logs.  When a "None" message is received, terminate
    # the loop which will signal the end of the child process.  The "None"
    # message will typically be generated at the end of the calling function
    # using the multiprocessing.Queue.put or put_nowait method to signal the
    # root logger to terminate.
    while True:
        try:
            log_record = msg_queue.get()
            if log_record is None:
                break
            root_logger = root_listener(log_record.name)
            root_logger.handle(log_record)
        except Exception:  # pylint: disable=broad-except
            # Some generic exception has been generated by the root logger.
            # This can likely be handled more gracefully in the future.
            print("Problem with root logger", file=sys_stderr)
            print_exc(file=sys_stderr)  # These are problematic from perflint


def process_csv(csv_file,
                netbox_url,
                netbox_token,
                message_queue=None,
                update_mode=True,
                loader_function=None,
                tls_verify=True):
    """
    Where the magic happens.

    Given a CSV file and supporting arguments, create a multiprocessing.Manager
    context and open the file.  For each row in the file, call the processing
    function in a new multiprocessing.Process instance.  As each instance
    is created, a reference to the process is stored in a list to be iterated
    at the end of CSV processing to wait for each outstanding task to
    complete.

    :param csv_file: CSV file to be processed
    :param netbox_url: Full URL of the NetBox instance
    :param netbox_token: API token for the NetBox instance
    :param message_queue: multiprocessing.Queue object reference. This is
        passed to the processing function for logging purposes.
    :param update_mode: Boolean - if a device already exists, should it be
        processes and updated with the values in the CSV, or skipped?
    :param loader_function: Reference to the processing function for each
        CSV row. The loader_function is what will be opened via
        multiprocessing.
    :param tls_verify: Boolean - Should TLS certificate validation be
        performed when consuming APIs via https?
    :return: None
    """
    # pylint: disable=too-many-arguments, fixme
    # TODO check on multiprocessing exceptions and graceful termination to prevent system hangs

    try:
        with MpManager():
            with open(csv_file, "r", encoding="utf-8-sig") as csvfile:
                reader = CsvDictReader(csvfile)

                worker_process_list = []
                for row in reader:
                    worker_process = MpProcess(target=loader_function,
                                               name=f"csv-line-{reader.line_num}",
                                               kwargs={"netbox_url": netbox_url,
                                                       "netbox_token": netbox_token,
                                                       "update_mode": update_mode,
                                                       "csv_row": row,
                                                       "tls_verify": tls_verify,
                                                       "msg_queue": message_queue,
                                                       "log_configurer": configure_worker_logging}
                                               )
                    worker_process.start()
                    worker_process_list.append(worker_process)

                for worker in worker_process_list:
                    worker.join()

    except FileNotFoundError as err:
        logger.error("Unable to open CSV file: %s", err)
    except Exception as err:  # pylint: disable=broad-except
        logger.error("Caught unhandled exception: %s", err)


if __name__ == "__main__":
    # pylint: disable=dotted-import-in-loop

    start_time = time() * 1000

    parser = ArgumentParser()
    parser.add_argument(
        "--no-update",
        dest="update_mode",
        default=True,
        action="store_false",
        help="Disable update mode (changes in CSV will not result in object updates)",
    )

    parser.add_argument(
        "-c",
        "--csv-file",
        dest="csv_file",
        default="netbox-import.csv",
        action="store",
        help="CSV file to import.  Default: netbox-import.csv",
    )

    parser.add_argument(
        "-n",
        "--no-tls-verify",
        "--no-validate-certs",
        dest="tls_verify",
        default=True,
        action="store_false",
        help="Disable TLS certificate chain validation.  Default: Enabled",
    )

    parser.add_argument(
        "-t",
        "--type",
        dest="device_type",
        default="access_point",
        action="store",
        choices=["access_point"],
        help="Type of device to import"
    )

    script_args = parser.parse_known_args()[0]

    queue = MpQueue(-1)
    log_listener = MpProcess(target=root_logging_process, args=(queue, configure_root_logging))
    log_listener.start()

    try:
        vault_netbox_secret = get_vault_secret(vault_url=VAULT_URL,
                                               vault_token=VAULT_TOKEN,
                                               secret_path=VAULT_NETBOX_PATH,
                                               tls_verify=script_args.tls_verify)
        vault_netbox_url = vault_netbox_secret["data"]["data"]["netbox_url"]
        vault_netbox_token = vault_netbox_secret["data"]["data"]["api_token"]
    except VaultError as vault_err:
        logger.error(
            "Unable to obtain NetBox secrets from vault.  Error details:\n%s", vault_err
        )
    else:
        process_csv(csv_file=script_args.csv_file,
                    netbox_url=vault_netbox_url,
                    netbox_token=vault_netbox_token,
                    message_queue=queue,
                    update_mode=script_args.update_mode,
                    loader_function=device_type_loader_mapping.get(script_args.device_type),
                    tls_verify=script_args.tls_verify)

    logger.debug("--- SCRIPT END TIME: %s ---", ((time() * 1000) - start_time))

    queue.put_nowait(None)
    log_listener.join()
