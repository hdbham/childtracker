"""
Migrate existing flat Firebase data to cfc/ prefix.
Copies: staff, assignments, logs, incidents, memos, files, meta
Then deletes the old root-level keys.

Run with:
    /usr/local/opt/python@3.11/bin/python3.11 migrate_to_cfc.py
"""

import toml
import firebase_admin
from firebase_admin import credentials, db

SECRETS_FILE = ".streamlit/secrets.toml"
DB_URL = "https://group-manager-a55a2-default-rtdb.firebaseio.com"

KEYS = ["staff", "assignments", "logs", "incidents", "memos", "files", "meta"]


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


def migrate():
    for key in KEYS:
        src = db.reference(key)
        dst = db.reference(f"cfc/{key}")

        data = src.get()
        if not data:
            print(f"  {key}: empty, skipping")
            continue

        # Don't overwrite if destination already has data
        existing = dst.get()
        if existing:
            print(f"  {key}: cfc/{key} already has data — skipping to avoid overwrite")
            continue

        dst.set(data)
        print(f"  {key}: copied {len(data) if isinstance(data, dict) else 1} record(s) → cfc/{key}")

    print("\nMigration complete. Deleting old root-level keys...")
    for key in KEYS:
        data = db.reference(key).get()
        if data:
            # Double-check destination has it before deleting
            dst_data = db.reference(f"cfc/{key}").get()
            if dst_data:
                db.reference(key).delete()
                print(f"  Deleted root /{key}")
            else:
                print(f"  WARNING: cfc/{key} empty — NOT deleting root /{key}")

    print("\nDone.")


if __name__ == "__main__":
    init_firebase()
    print("Migrating root-level data → cfc/...\n")
    migrate()
