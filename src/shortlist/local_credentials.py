"""Local operator-owned provider settings; never a hosted credential service."""
import ctypes
import os
import re
import sqlite3
import stat
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import SecretStr

if TYPE_CHECKING:
    from shortlist.config import Settings


class CredentialUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("Local provider settings could not be read or saved")


def validate_tavily_key(key: str) -> SecretStr:
    if not re.fullmatch(r"tvly-[A-Za-z0-9_-]{8,251}", key):
        raise ValueError("Enter a valid tvly-prefixed Tavily API key")
    return SecretStr(key)


def _dpapi(payload: bytes, *, decrypt: bool) -> bytes:
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = (ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob))
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
    source, result = Blob(len(payload), buffer), Blob()
    try:
        # UI forbidden, no machine-wide flag. API/worker share the current OS user.
        if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
            raise CredentialUnavailable()
        return ctypes.string_at(result.data, result.size)
    finally:
        ctypes.memset(buffer, 0, len(payload))
        if result.data:
            ctypes.memset(result.data, 0, result.size)
            kernel.LocalFree(result.data)


class LocalCredentials:
    def __init__(self, database_path: Path):
        self.path = Path(str(database_path.resolve()) + ".providers")

    def _check_file(self):
        if self.path.is_symlink():
            raise CredentialUnavailable()
        info = self.path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 131072:
            raise CredentialUnavailable()
        if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise CredentialUnavailable()

    def read(self) -> SecretStr | None:
        try:
            if self.path.is_symlink():
                raise CredentialUnavailable()
            if not self.path.exists():
                return None
            self._check_file()
            db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5)
            try:
                row = db.execute("SELECT payload FROM local_provider WHERE id=1").fetchone()
            finally:
                db.close()
            if row is None or not isinstance(row[0], bytes) or len(row[0]) > 4096:
                raise CredentialUnavailable()
            payload = row[0]
            if os.name == "nt" and payload.startswith(b"SHORTLIST-DPAPI1\n"):
                plain = _dpapi(payload.removeprefix(b"SHORTLIST-DPAPI1\n"), decrypt=True)
            elif os.name != "nt" and payload.startswith(b"SHORTLIST-PRIVATE1\n"):
                plain = payload.removeprefix(b"SHORTLIST-PRIVATE1\n")
            else:
                raise CredentialUnavailable()
            return validate_tavily_key(plain.decode("ascii"))
        except (OSError, ValueError, sqlite3.Error) as exc:
            raise CredentialUnavailable() from exc

    def save(self, key: SecretStr):
        plain = validate_tavily_key(key.get_secret_value()).get_secret_value().encode("ascii")
        payload = b"SHORTLIST-DPAPI1\n" + _dpapi(plain, decrypt=False) if os.name == "nt" \
            else b"SHORTLIST-PRIVATE1\n" + plain
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
            except FileExistsError:
                pass
            self._check_file()
            db = sqlite3.connect(self.path, timeout=5)
            try:
                db.execute("CREATE TABLE IF NOT EXISTS local_provider(id INTEGER PRIMARY KEY CHECK(id=1),payload BLOB NOT NULL)")
                db.execute("BEGIN IMMEDIATE")
                db.execute("INSERT INTO local_provider(id,payload) VALUES (1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", (payload,))
                db.commit()
            finally:
                db.close()
        except (OSError, sqlite3.Error) as exc:
            raise CredentialUnavailable() from exc


def apply_local_credentials(settings: "Settings") -> "Settings":
    if settings.mode == "hosted":
        return settings
    key = LocalCredentials(settings.db_path).read()
    return settings.model_copy(update={"search_provider": "tavily", "tavily_key": key}) if key else settings
