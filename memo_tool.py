"""
MCP memo tool — push a memo to all staff on a given date.

Usage:
    python memo_tool.py --site <group|polk> --date <YYYY-MM-DD> --memo "Memo text here"

Sites:
    group  →  group-manager-a55a2  (main.py app)
    polk   →  polksdc               (polkmain.py app)
"""

import argparse
import toml
import firebase_admin
from firebase_admin import credentials, db

SITES = {
    "group": {
        "secrets": ".streamlit/secrets.toml",
        "db_url": "https://group-manager-a55a2-default-rtdb.firebaseio.com",
    },
    "polk": {
        "secrets": ".streamlit/secrets2.toml",
        "db_url": "https://polksdc-default-rtdb.firebaseio.com/",
    },
}


def init_firebase(site_key):
    cfg = SITES[site_key]
    raw = toml.load(cfg["secrets"])["firebase"]
    cred_dict = {k: raw[k] for k in (
        "type", "project_id", "private_key_id", "private_key",
        "client_email", "client_id", "auth_uri", "token_uri",
        "auth_provider_x509_cert_url", "client_x509_cert_url",
    )}
    cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")

    app_name = f"memo_tool_{site_key}"
    if app_name not in [a.name for a in firebase_admin._apps.values()]:
        firebase_admin.initialize_app(credentials.Certificate(cred_dict), {
            "databaseURL": cfg["db_url"]
        }, name=app_name)
    return firebase_admin.get_app(app_name)


def push_memos(site_key, date_iso, memo_text):
    app = init_firebase(site_key)
    staff_ref = db.reference("staff", app=app)
    memos_ref = db.reference("memos", app=app)

    staff_data = staff_ref.get() or {}
    staff_names = [v["name"] for v in staff_data.values() if "name" in v]

    if not staff_names:
        print(f"No staff found in {site_key}.")
        return

    existing_memos = memos_ref.get() or {}

    updated, created = 0, 0
    for name in staff_names:
        existing_key = next(
            (k for k, v in existing_memos.items()
             if v.get("staff") == name and v.get("date") == date_iso),
            None
        )
        payload = {"staff": name, "date": date_iso, "memo": memo_text}
        if existing_key:
            memos_ref.child(existing_key).update(payload)
            updated += 1
        else:
            memos_ref.push(payload)
            created += 1

    print(f"[{site_key}] {date_iso} — {created} created, {updated} updated")
    print(f"Staff: {', '.join(staff_names)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Push memo to all staff at a site.")
    parser.add_argument("--site", choices=list(SITES.keys()), required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--memo", required=True, help="Memo content")
    args = parser.parse_args()
    push_memos(args.site, args.date, args.memo)
