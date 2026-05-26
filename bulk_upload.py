"""
Bulk upload all PDFs and docx files from Summer_Camp_2026_Ogden to Firebase Storage.
Saves URL + metadata to Firebase Realtime DB under 'files'.

Run with:
    /usr/local/opt/python@3.11/bin/python3.11 bulk_upload.py
"""

import os
import re
import uuid
import urllib.parse
import toml
import firebase_admin
from firebase_admin import credentials, db, storage

CAMP_ROOT = "/Users/admin/Desktop/Summer_Camp_2026_Ogden"
SECRETS_FILE = ".streamlit/secrets.toml"
DB_URL = "https://group-manager-a55a2-default-rtdb.firebaseio.com"
BUCKET = "group-manager-a55a2.firebasestorage.app"

MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

def parse_date(folder_name):
    """Parse 'Jun01_Mon_ONSITE_Camp_Day' -> '2026-06-01'"""
    m = re.match(r'^([A-Z][a-z]{2})(\d{2})_', folder_name)
    if m:
        month = MONTH_MAP.get(m.group(1))
        day = m.group(2)
        if month:
            return f"2026-{month}-{day}"
    return None

def init_firebase():
    raw = toml.load(SECRETS_FILE)["firebase"]
    cred_dict = {k: raw[k] for k in (
        "type", "project_id", "private_key_id", "private_key",
        "client_email", "client_id", "auth_uri", "token_uri",
        "auth_provider_x509_cert_url", "client_x509_cert_url",
    )}
    cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
    firebase_admin.initialize_app(credentials.Certificate(cred_dict), {
        "databaseURL": DB_URL,
        "storageBucket": BUCKET,
    })

def upload_all():
    init_firebase()
    bucket = storage.bucket()
    files_ref = db.reference("files")

    # Load existing files to avoid re-uploading duplicates
    existing = files_ref.get() or {}
    existing_names = {v.get("name") for v in existing.values() if v.get("name")}

    uploaded = 0
    skipped = 0
    errors = 0

    for session_dir in sorted(os.listdir(CAMP_ROOT)):
        session_path = os.path.join(CAMP_ROOT, session_dir)
        if not os.path.isdir(session_path):
            continue
        if session_dir.startswith("Session_"):
            session_label = session_dir.replace("_", " ")
        else:
            session_label = session_dir

        for day_dir in sorted(os.listdir(session_path)):
            day_path = os.path.join(session_path, day_dir)
            if not os.path.isdir(day_path):
                continue

            date_iso = parse_date(day_dir)
            day_label = day_dir.replace("_", " ")

            # Walk all subdirs within the day folder
            for root, dirs, files in os.walk(day_path):
                for filename in sorted(files):
                    if not (filename.endswith(".pdf") or filename.endswith(".docx")):
                        continue
                    if filename.startswith("."):
                        continue

                    if filename in existing_names:
                        print(f"  SKIP (exists): {filename}")
                        skipped += 1
                        continue

                    local_path = os.path.join(root, filename)
                    # Storage path: camp/YYYY-MM-DD/filename (or camp/no-date/session/filename)
                    if date_iso:
                        storage_path = f"camp/{date_iso}/{filename}"
                    else:
                        storage_path = f"camp/extra/{session_dir}/{filename}"

                    try:
                        blob = bucket.blob(storage_path)
                        content_type = "application/pdf" if filename.endswith(".pdf") else \
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        download_token = str(uuid.uuid4())
                        blob.metadata = {"firebaseStorageDownloadTokens": download_token}
                        blob.upload_from_filename(local_path, content_type=content_type)
                        blob.patch()  # apply metadata
                        encoded_path = urllib.parse.quote(storage_path, safe="")
                        url = (
                            f"https://firebasestorage.googleapis.com/v0/b/{BUCKET}"
                            f"/o/{encoded_path}?alt=media&token={download_token}"
                        )

                        files_ref.push({
                            "date": date_iso or "",
                            "label": day_label if date_iso else session_label,
                            "session": session_label,
                            "name": filename,
                            "url": url,
                        })

                        print(f"  OK: {filename} -> {date_iso or 'extra'}")
                        uploaded += 1
                    except Exception as e:
                        print(f"  ERROR: {filename}: {e}")
                        errors += 1

    print(f"\nDone: {uploaded} uploaded, {skipped} skipped, {errors} errors")

if __name__ == "__main__":
    upload_all()
