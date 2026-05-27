"""
Copies file metadata from root /files → cfc/files.
The bulk_upload.py wrote to /files; the app reads from cfc/files.

Run with:
    /usr/local/opt/python@3.11/bin/python3.11 sync_files_to_cfc.py
"""

import toml
import firebase_admin
from firebase_admin import credentials, db

SECRETS_FILE = ".streamlit/secrets.toml"
DB_URL = "https://group-manager-a55a2-default-rtdb.firebaseio.com"


def init_firebase():
    raw = toml.load(SECRETS_FILE)["firebase"]
    cred_dict = {k: raw[k] for k in (
        "type", "project_id", "private_key_id", "private_key",
        "client_email", "client_id", "auth_uri", "token_uri",
        "auth_provider_x509_cert_url", "client_x509_cert_url",
    )}
    cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(cred_dict), {"databaseURL": DB_URL})


def sync():
    src = db.reference("files")
    dst = db.reference("cfc/files")

    data = src.get()
    if not data:
        print("No data in root /files — nothing to sync.")
        return

    existing = dst.get() or {}
    existing_names = {v.get("name") for v in existing.values() if v.get("name")}

    copied = 0
    skipped = 0
    for v in data.values():
        if v.get("name") in existing_names:
            skipped += 1
            continue
        dst.push(v)
        copied += 1

    print(f"Done: {copied} copied, {skipped} already existed in cfc/files")


if __name__ == "__main__":
    init_firebase()
    sync()
