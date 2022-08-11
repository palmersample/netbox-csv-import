"""
Helper functions to interact with HashiCorp vault
"""
from logging import getLogger
from requests.exceptions import ConnectionError as RequestsConnectionError
from hvac import Client as vault_client
from hvac.exceptions import VaultError, InvalidPath as VaultInvalidPath

logger = getLogger(__name__)


def get_vault_secret(vault_url, vault_token, secret_path, tls_verify=True):
    """
    Wrapper function for "hvac" to obtain a secret from Vault located at
    secret_path.

    :param vault_url: Full URL of the Vault instance
    :param vault_token: Token used for Vault authentication.  Note: this should
        be updated in the future to use AppRole or similar auth methods.
    :param secret_path: Path of the secret to retrieve.
    :param tls_verify: Boolean - whether to validate TLS cert chain
    :raises:
        VaultError: from exceptions caught while trying to retrieve the desired
            secret.
    :return: Retrieves secret on success
    """
    # Initialize Vault API
    vault = vault_client(url=vault_url, token=vault_token, verify=tls_verify)

    try:
        secret = vault.secrets.kv.v2.read_secret_version(path=secret_path)

    except VaultInvalidPath as vault_err:
        # Invalid path specified for the Vault secret
        raise VaultError from vault_err
    except VaultError as vault_err:
        # Error obtaining secret from Vault.
        raise VaultError from vault_err
    except RequestsConnectionError as vault_err:
        # Error connecting to vault
        raise VaultError(f"Unable to connect to Vault instance - "
                         f"Check VAULT_URL environment variable?\n"
                         f"{vault_err}") from vault_err
    except KeyError as vault_err:
        # Requested key not present in the Vault response
        raise VaultError from vault_err

    return secret
