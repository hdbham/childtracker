"""
Load test: simulate 3 sites × 7 staff × ~15 kids each doing concurrent
sign-ins, sign-outs, moves, and location updates. Measures p50/p95/max latency.

Run with:
    /usr/local/opt/python@3.11/bin/python3.11 load_test.py
"""

import time
import random
import threading
import statistics
import toml
import firebase_admin
from firebase_admin import credentials, db

SECRETS_FILE = ".streamlit/secrets.toml"
DB_URL = "https://group-manager-a55a2-default-rtdb.firebaseio.com"

SITES = ["ogden", "provo", "slc"]
STAFF_PER_SITE = 7
KIDS_PER_STAFF = 15
OPERATIONS_PER_SITE = 60  # total ops to fire per site

latencies = []
errors = []
lock = threading.Lock()


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


def timed(label, fn):
    t0 = time.time()
    try:
        fn()
        ms = (time.time() - t0) * 1000
        with lock:
            latencies.append((label, ms))
        return ms
    except Exception as e:
        with lock:
            errors.append(f"{label}: {e}")
        return None


def seed_site(site):
    """Push fake staff + children for this site."""
    staff_ref = db.reference(f"test/{site}/staff")
    assign_ref = db.reference(f"test/{site}/assignments")
    staff_ref.delete()
    assign_ref.delete()

    staff_keys = []
    for s in range(STAFF_PER_SITE):
        k = staff_ref.push({"name": f"Staff_{site}_{s}", "location": "Gym"}).key
        staff_keys.append(k)
        for c in range(KIDS_PER_STAFF):
            assign_ref.push({"staff": f"Staff_{site}_{s}", "child": f"Kid_{site}_{s}_{c}", "site": site})

    return staff_keys


def run_site_ops(site, n_ops):
    assign_ref = db.reference(f"test/{site}/assignments")
    staff_ref = db.reference(f"test/{site}/staff")
    logs_ref = db.reference(f"test/{site}/logs")

    staff_names = [f"Staff_{site}_{i}" for i in range(STAFF_PER_SITE)]

    for op_num in range(n_ops):
        op = random.choice(["read", "read", "read", "checkin", "checkout", "move", "location"])
        # weight reads 3x — reflects real usage

        if op == "read":
            timed(f"{site}/read", lambda: assign_ref.get())

        elif op == "checkin":
            name = f"Kid_new_{site}_{op_num}_{random.randint(0,9999)}"
            staff = random.choice(staff_names)
            timed(f"{site}/checkin", lambda: assign_ref.push({"staff": staff, "child": name, "site": site}))

        elif op == "checkout":
            def do_checkout():
                kids = assign_ref.get() or {}
                if kids:
                    key = random.choice(list(kids.keys()))
                    assign_ref.child(key).delete()
                    logs_ref.push({"action": "checkout", "child": kids[key].get("child")})
            timed(f"{site}/checkout", do_checkout)

        elif op == "move":
            def do_move():
                kids = assign_ref.get() or {}
                if kids:
                    key = random.choice(list(kids.keys()))
                    new_staff = random.choice(staff_names)
                    assign_ref.child(key).update({"staff": new_staff})
            timed(f"{site}/move", do_move)

        elif op == "location":
            def do_location():
                staff_data = staff_ref.get() or {}
                if staff_data:
                    key = random.choice(list(staff_data.keys()))
                    staff_ref.child(key).update({"location": random.choice(["Gym", "Cafeteria", "Field", "Library"])})
            timed(f"{site}/location", do_location)


def cleanup(sites):
    for site in sites:
        db.reference(f"test/{site}").delete()
    print("Cleaned up test data.")


def report():
    if not latencies:
        print("No results recorded.")
        return

    all_ms = [ms for _, ms in latencies]
    by_op = {}
    for label, ms in latencies:
        op = label.split("/")[1]
        by_op.setdefault(op, []).append(ms)

    print(f"\n{'='*50}")
    print(f"  LOAD TEST RESULTS  ({len(latencies)} operations, {len(SITES)} sites)")
    print(f"{'='*50}")
    print(f"  Overall   p50={statistics.median(all_ms):.0f}ms  "
          f"p95={sorted(all_ms)[int(len(all_ms)*0.95)]:.0f}ms  "
          f"max={max(all_ms):.0f}ms")
    print()
    for op, times in sorted(by_op.items()):
        s = sorted(times)
        print(f"  {op:<12} n={len(times):>3}  "
              f"p50={statistics.median(s):.0f}ms  "
              f"p95={s[int(len(s)*0.95)]:.0f}ms  "
              f"max={max(s):.0f}ms")
    if errors:
        print(f"\n  Errors ({len(errors)}):")
        for e in errors[:10]:
            print(f"    {e}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    init_firebase()
    print(f"Seeding {len(SITES)} sites × {STAFF_PER_SITE} staff × {KIDS_PER_STAFF} kids...")
    for site in SITES:
        seed_site(site)
    print(f"Seeded. Firing {OPERATIONS_PER_SITE} ops/site concurrently across all sites...\n")

    threads = [
        threading.Thread(target=run_site_ops, args=(site, OPERATIONS_PER_SITE))
        for site in SITES
    ]
    t_start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total_s = time.time() - t_start

    print(f"All ops complete in {total_s:.1f}s ({len(latencies)} total ops)")
    report()
    cleanup(SITES)
