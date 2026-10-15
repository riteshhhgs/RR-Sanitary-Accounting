
import hashlib
import secrets
import getpass
from pathlib import Path

def make_password_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        600_000
    ).hex()

owner_password = getpass.getpass("Create OWNER password: ")
staff_password = getpass.getpass("Create STAFF password: ")

if len(owner_password) < 12 or len(staff_password) < 12:
    raise SystemExit("Use passwords of at least 12 characters.")

if owner_password == staff_password:
    raise SystemExit("Owner and staff passwords must be different.")

owner_salt = secrets.token_hex(16)
staff_salt = secrets.token_hex(16)

owner_hash = make_password_hash(owner_password, owner_salt)
staff_hash = make_password_hash(staff_password, staff_salt)

print("\nCopy these settings into .streamlit/secrets.toml:\n")
print("[auth]")
print(f'owner_salt = "{owner_salt}"')
print(f'owner_hash = "{owner_hash}"')
print(f'staff_salt = "{staff_salt}"')
print(f'staff_hash = "{staff_hash}"')
