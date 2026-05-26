"""
Read all files from Firebase DB, then rewrite MASTER_ACTIVITY_CALENDAR.md
so each activity name becomes a markdown link to its PDF.

Run with:
    /usr/local/opt/python@3.11/bin/python3.11 inject_links.py
"""

import re
import toml
import firebase_admin
from firebase_admin import credentials, db

SECRETS_FILE = ".streamlit/secrets.toml"
DB_URL = "https://group-manager-a55a2-default-rtdb.firebaseio.com"
CALENDAR_PATH = "/Users/admin/Desktop/Summer_Camp_2026_Ogden/MASTER_ACTIVITY_CALENDAR.md"


def normalize(s):
    """Lower-case, strip punctuation/extra spaces for fuzzy matching."""
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def init_firebase():
    raw = toml.load(SECRETS_FILE)["firebase"]
    cred_dict = {k: raw[k] for k in (
        "type", "project_id", "private_key_id", "private_key",
        "client_email", "client_id", "auth_uri", "token_uri",
        "auth_provider_x509_cert_url", "client_x509_cert_url",
    )}
    cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(cred_dict), {
            "databaseURL": DB_URL,
        })


def build_link_map():
    """Returns dict: normalized_activity_name -> url"""
    files_ref = db.reference("files")
    all_files = files_ref.get() or {}

    link_map = {}
    for v in all_files.values():
        filename = v.get("name", "")
        url = v.get("url", "")
        if not url:
            continue
        # Strip file extension
        stem = re.sub(r"\.(pdf|docx)$", "", filename, flags=re.IGNORECASE)
        # Strip trailing type label like " - Literacy", " -STEM", " (Arts)", etc.
        clean = re.sub(
            r"\s*[-–—(]\s*(literacy|stem|arts?|physical activity|activity|craft|field trip|art & craft|art and craft|games?|game day|backpocket games?|science|social emotional|sel|reading)[^)]*\)?$",
            "", stem, flags=re.IGNORECASE
        ).strip()
        key = normalize(clean)
        if key:
            link_map[key] = url

    print(f"Built link map with {len(link_map)} entries")
    return link_map


def inject_links(link_map):
    with open(CALENDAR_PATH, "r") as f:
        lines = f.readlines()

    # Match table rows: | Activity Name | Type |
    # We only linkify the activity cell (first column after leading |)
    table_row_re = re.compile(r"^\| (.+?) \| (.+?) \|")
    already_linked_re = re.compile(r"\[.+?\]\(.+?\)")

    updated = 0
    new_lines = []
    for line in lines:
        m = table_row_re.match(line)
        if m and not already_linked_re.search(line):
            activity = m.group(1).strip()
            if activity.lower() in ("activity", "---"):
                new_lines.append(line)
                continue
            key = normalize(activity)
            url = link_map.get(key)
            if not url:
                # Try partial match: find any key that contains the normalized activity
                matches = [v for k, v in link_map.items() if key in k or k in key]
                if matches:
                    url = matches[0]
            if url:
                linked_activity = f"[{activity}]({url})"
                new_line = line.replace(f"| {activity} |", f"| {linked_activity} |", 1)
                new_lines.append(new_line)
                updated += 1
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    with open(CALENDAR_PATH, "w") as f:
        f.writelines(new_lines)

    print(f"Injected {updated} links into {CALENDAR_PATH}")


if __name__ == "__main__":
    init_firebase()
    link_map = build_link_map()
    inject_links(link_map)
