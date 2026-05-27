"""
Stress test Firebase across cfc/polk/davis sites.
Simulates concurrent reads and writes: assignments, logs, bathroom flags, moves.

Run with:
    /usr/local/opt/python@3.11/bin/python3.11 stress_test.py
"""

import toml
import time
import random
import threading
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime

SECRETS_FILE = ".streamlit/secrets.toml"
DB_URL = "https://group-manager-a55a2-default-rtdb.firebaseio.com"
SITES = ["cfc", "polk", "davis"]
FAKE_STAFF = ["Alice", "Bob", "Carmen", "Diego", "Eva"]
FAKE_CHILDREN = [f"Child_{i:02d}" for i in range(1, 31)]

results = {"ok": 0, "err": 0, "latencies": []}
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


def record(ok, latency_ms):
    with lock:
        if ok:
            results["ok"] += 1
        else:
            results["err"] += 1
        results["latencies"].append(latency_ms)


def op_add_child(site):
    child = random.choice(FAKE_CHILDREN)
    staff = random.choice(FAKE_STAFF)
    t = time.time()
    try:
        ref = db.reference(f"{site}/assignments")
        ref.push({"staff": staff, "child": child, "bathroom": False})
        record(True, (time.time() - t) * 1000)
        return True, child, staff
    except Exception as e:
        record(False, (time.time() - t) * 1000)
        return False, None, None


def op_read_assignments(site):
    t = time.time()
    try:
        db.reference(f"{site}/assignments").get()
        record(True, (time.time() - t) * 1000)
    except Exception:
        record(False, (time.time() - t) * 1000)


def op_log(site, staff, child, action):
    t = time.time()
    try:
        db.reference(f"{site}/logs").push({
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "staff": staff,
            "child": child,
            "notes": f"Stress test: {action}",
        })
        record(True, (time.time() - t) * 1000)
    except Exception:
        record(False, (time.time() - t) * 1000)


def op_bathroom_flag(site, child_id):
    t = time.time()
    try:
        db.reference(f"{site}/assignments/{child_id}").update({"bathroom": True})
        record(True, (time.time() - t) * 1000)
    except Exception:
        record(False, (time.time() - t) * 1000)


def op_move(site, child_id):
    new_staff = random.choice(FAKE_STAFF)
    t = time.time()
    try:
        db.reference(f"{site}/assignments/{child_id}").update({"staff": new_staff})
        record(True, (time.time() - t) * 1000)
    except Exception:
        record(False, (time.time() - t) * 1000)


def op_delete_child(site, child_id):
    t = time.time()
    try:
        db.reference(f"{site}/assignments/{child_id}").delete()
        record(True, (time.time() - t) * 1000)
    except Exception:
        record(False, (time.time() - t) * 1000)


def site_worker(site, n_ops):
    child_ids = []

    for _ in range(n_ops):
        action = random.choices(
            ["add", "read", "bathroom", "move", "delete"],
            weights=[30, 40, 10, 15, 5],
        )[0]

        if action == "add":
            ok, child, staff = op_add_child(site)
            if ok:
                # Fetch the key we just pushed
                data = db.reference(f"{site}/assignments").order_by_child("child").equal_to(child).get()
                if data:
                    kid_id = list(data.keys())[-1]
                    child_ids.append((kid_id, child, staff))

        elif action == "read":
            op_read_assignments(site)

        elif action == "bathroom" and child_ids:
            kid_id, child, staff = random.choice(child_ids)
            op_bathroom_flag(site, kid_id)
            op_log(site, staff, child, "BATHROOM")

        elif action == "move" and child_ids:
            kid_id, child, staff = random.choice(child_ids)
            op_move(site, kid_id)
            new_staff = random.choice(FAKE_STAFF)
            op_log(site, new_staff, child, "Move")

        elif action == "delete" and child_ids:
            idx = random.randrange(len(child_ids))
            kid_id, child, staff = child_ids.pop(idx)
            op_delete_child(site, kid_id)
            op_log(site, staff, child, "Checkout")

        time.sleep(random.uniform(0.02, 0.1))

    # Cleanup: remove any remaining test children
    for kid_id, _, _ in child_ids:
        try:
            db.reference(f"{site}/assignments/{kid_id}").delete()
        except Exception:
            pass


def run_stress(ops_per_site=50, threads_per_site=3):
    print(f"\n🔥 Stress test: {threads_per_site} threads × {SITES} sites × {ops_per_site} ops each")
    print(f"   Total planned ops: ~{threads_per_site * len(SITES) * ops_per_site}\n")

    threads = []
    for site in SITES:
        for _ in range(threads_per_site):
            t = threading.Thread(target=site_worker, args=(site, ops_per_site))
            threads.append(t)

    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - start

    lats = sorted(results["latencies"])
    total = results["ok"] + results["err"]
    p50 = lats[int(len(lats) * 0.50)] if lats else 0
    p95 = lats[int(len(lats) * 0.95)] if lats else 0
    p99 = lats[int(len(lats) * 0.99)] if lats else 0

    print("=" * 50)
    print(f"  Total ops:   {total}")
    print(f"  ✅ OK:        {results['ok']}")
    print(f"  ❌ Errors:    {results['err']}")
    print(f"  Elapsed:     {elapsed:.1f}s")
    print(f"  Throughput:  {total/elapsed:.1f} ops/sec")
    print(f"  Latency p50: {p50:.0f}ms")
    print(f"  Latency p95: {p95:.0f}ms")
    print(f"  Latency p99: {p99:.0f}ms")
    print("=" * 50)


if __name__ == "__main__":
    init_firebase()
    run_stress(ops_per_site=50, threads_per_site=3)
