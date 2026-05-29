import streamlit as st
import firebase_admin
from firebase_admin import credentials, db, storage
import pandas as pd
import datetime
import duckdb
import uuid
import urllib.parse
from pytz import timezone

try:
    ADMIN_PIN = str(st.secrets["ADMIN_PIN"]).strip()
except:
    ADMIN_PIN = ""
try:
    CHECKOUT_PIN = str(st.secrets["CHECKOUT_PIN"]).strip()
except:
    CHECKOUT_PIN = ""

st.set_page_config(page_title="SDC Manager", page_icon="🏕️", layout="centered")

# --- PWA (injected after site is known) ---
def _inject_pwa(site_label):
    st.markdown(f"""
<link rel="manifest" href="/app/static/manifest.json">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="SDC {site_label}">
<link rel="apple-touch-icon" href="/app/static/icon-192.png">
""", unsafe_allow_html=True)

# --- CONFIG ---
MT = timezone("US/Mountain")

# --- SITE ROUTING ---
SITES = {
    "cfc":   {"label": "CFC",   "color": "#ff4b4b"},
    "polk":  {"label": "Polk",  "color": "#4b8bff"},
    "davis": {"label": "Davis", "color": "#4bcc6f"},
}
site = st.query_params.get("site", "cfc").lower()
if site not in SITES:
    st.error(f"Unknown site '{site}'. Use ?site=cfc, ?site=polk, or ?site=davis")
    st.stop()
SITE_LABEL = SITES[site]["label"]
_inject_pwa(SITE_LABEL)

# --- LOCATION OPTIONS ---
LOCATIONS = [
    "Classroom 1",
    "Classroom 2",
    "Classroom 3"
    "Playground",
    "School Yard"
    "Cafeteria",
    "Field",
    "Pool",
    "Bus",
    "Bathroom"
]

def now_timestamp():
    return datetime.datetime.now(MT).strftime("%B %d, %Y %I:%M %p")

def today_date():
    return datetime.datetime.now(MT).date().isoformat()

# --- FIREBASE INITIALIZATION ---
firebase_secret = st.secrets["firebase"]
cred = credentials.Certificate({
    "type": firebase_secret["type"],
    "project_id": firebase_secret["project_id"],
    "private_key_id": firebase_secret["private_key_id"],
    "private_key": firebase_secret["private_key"].replace('\\n', '\n'),
    "client_email": firebase_secret["client_email"],
    "client_id": firebase_secret["client_id"],
    "auth_uri": firebase_secret["auth_uri"],
    "token_uri": firebase_secret["token_uri"],
    "auth_provider_x509_cert_url": firebase_secret["auth_provider_x509_cert_url"],
    "client_x509_cert_url": firebase_secret["client_x509_cert_url"]
})

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://group-manager-a55a2-default-rtdb.firebaseio.com',
        'storageBucket': 'group-manager-a55a2.firebasestorage.app'
    })

staff_ref = db.reference(f"{site}/staff")
assignments_ref = db.reference(f"{site}/assignments")
logs_ref = db.reference(f"{site}/logs")
incidents_ref = db.reference(f"{site}/incidents")
memos_ref = db.reference(f"{site}/memos")
files_ref = db.reference(f"{site}/files")
sop_ref = db.reference(f"{site}/sop_files")
training_ref = db.reference(f"{site}/training_files")
meta_ref = db.reference(f"{site}/meta")

# --- CACHED FIREBASE READS (TTL = 8s, busted on mutation via st.cache_data.clear()) ---
@st.cache_data(ttl=8, show_spinner=False)
def fetch_staff():
    try:
        return staff_ref.get() or {}
    except Exception:
        return {}

@st.cache_data(ttl=8, show_spinner=False)
def fetch_assignments():
    try:
        return assignments_ref.get() or {}
    except Exception:
        return {}

@st.cache_data(ttl=8, show_spinner=False)
def fetch_memos():
    try:
        return memos_ref.get() or {}
    except Exception:
        return {}

@st.cache_data(ttl=30, show_spinner=False)
def fetch_files():
    try:
        return files_ref.get() or {}
    except Exception:
        return {}

@st.cache_data(ttl=30, show_spinner=False)
def fetch_sop_files():
    try:
        return sop_ref.get() or {}
    except Exception:
        return {}

@st.cache_data(ttl=30, show_spinner=False)
def fetch_training_files():
    try:
        return training_ref.get() or {}
    except Exception:
        return {}

def safe_get(ref):
    try:
        return ref.get() or {}
    except Exception:
        return {}

def safe_write(fn):
    """Wrap any Firebase write; clears cache so next read is fresh."""
    try:
        fn()
        st.cache_data.clear()
    except Exception as e:
        st.error(f"⚠️ Save failed — try again. ({e})")

def rerun():
    """Clear cache then rerun so mutations are always visible immediately."""
    st.cache_data.clear()
    st.rerun()

# --- NEW DAY PROMPT ---
_today = datetime.datetime.now(MT).date().isoformat()
try:
    _last_cleared = meta_ref.child("last_cleared_date").get() or ""
except Exception:
    _last_cleared = _today  # assume cleared on error to avoid loop

if _last_cleared != _today:
    st.warning("🌅 New day — clear all assignments?")
    if st.button("Yes, Clear Assignments"):
        def _clear():
            assignments_ref.delete()
            meta_ref.child("last_cleared_date").set(_today)
            logs_ref.push({
                "timestamp": datetime.datetime.now(MT).isoformat(),
                "action": "AUTO_CLEAR",
                "staff": "System",
                "child": "ALL",
                "notes": f"Assignments cleared for {_today}"
            })
        safe_write(_clear)
        rerun()

# --- LOAD STAFF DATA ---
staff_data_raw = fetch_staff()
staff_lookup = {v["name"]: v.get("location", "N/A") for v in staff_data_raw.values() if "name" in v}
STAFF = list(staff_lookup.keys())

# --- LOAD ASSIGNMENTS DATA ---
assignments_raw = fetch_assignments()
rows = []
for k, v in assignments_raw.items():
    rows.append({
        "id": k,
        "staff": v.get("staff", ""),
        "child": v.get("child", ""),
        "bathroom": v.get("bathroom", False)
    })
data = pd.DataFrame(rows, columns=["id", "staff", "child", "bathroom"])

#test
# --- PAGE NAVIGATION ---
_nav = ["👩‍🏫 Staff View", "📊 Admin View"]
if site == "cfc":
    _nav += ["📅 My Memos", "📁 Resources"]
_nav += ["ℹ️ How to Use"]
page = st.sidebar.radio("📂 Navigate", _nav)

# STAFF VIEW
if page == "👩‍🏫 Staff View":
    st.title(f"SDC Dashboard — {SITE_LABEL} 😎")
    staff = st.selectbox("Select Staff", STAFF, key="selected_staff")
    if not staff: st.stop()

    memos_data = fetch_memos()
    today_iso = today_date()
    todays_memo = ""
    for v in memos_data.values():
        if v.get("staff") == "Hunter" and v.get("date") == today_iso:
            todays_memo = v.get("memo", "")
            break

    if todays_memo and site == "cfc":
        with st.sidebar:
            st.divider()
            st.markdown("### 📋 Today's Memo")
            st.markdown(todays_memo)

    staff_location = staff_lookup.get(staff, "N/A")
    new_location = st.text_input("Location:", value=staff_location)

    if staff_location != new_location:
        for key, value in staff_data_raw.items():
            if value["name"] == staff:
                staff_ref.child(key).update({"location": new_location})
                logs_ref.push({
                    "timestamp": now_timestamp(),
                    "action": "Location Update",
                    "staff": staff,
                    "child": "[LOCATION UPDATE]",
                    "notes": f"Updated location to {new_location}"
                })
                break
        rerun()

    staff_assignments = data[data["staff"] == staff]
    rows_with_index = staff_assignments.to_dict(orient="records")

    st.info("""
    - **KEEP LOCATION UPDATED 🎯**
    - 🧑‍🤝‍🧑 Count heads
    - ☀️ Sunscreen outside every time
    - 💧 Hydrate between transitions
    - ✅ Log everything
    - 📢 Announce changes on walkie
    """)

    # --- BULK ACTIONS ---
    st.divider()
    st.subheader("⚡ Bulk Actions", divider="gray")

    # All children at this site with id lookup
    all_rows = data.to_dict(orient="records")
    all_name_to_id = {r["child"]: r["id"] for r in all_rows}
    all_staff_with_kids = [s for s in STAFF if s and not data[data["staff"] == s].empty]
    child_to_staff = {r["child"]: r["staff"] for r in all_rows}

    DIVIDER_PREFIX = "§div§"
    grouped_options = []
    all_child_names = []
    for s in all_staff_with_kids:
        grouped_options.append(f"{DIVIDER_PREFIX}{s}")
        children = list(data[data["staff"] == s]["child"])
        grouped_options.extend(children)
        all_child_names.extend(children)

    def _fmt(opt):
        if opt.startswith(DIVIDER_PREFIX):
            return f"── {opt[len(DIVIDER_PREFIX):]} ──"
        return f"  {opt}"

    # Expand any dividers before rendering the widget
    _pre = st.session_state.get("bulk_select", [])
    _divs = [n for n in _pre if n.startswith(DIVIDER_PREFIX)]
    if _divs:
        _real = [n for n in _pre if not n.startswith(DIVIDER_PREFIX)]
        _added = []
        for div in _divs:
            _added.extend(list(data[data["staff"] == div[len(DIVIDER_PREFIX):]]["child"]))
        st.session_state["bulk_select"] = list(dict.fromkeys(_real + _added))

    selected_raw = st.multiselect(
        "Children:",
        options=grouped_options,
        format_func=_fmt,
        key="bulk_select",
        label_visibility="collapsed",
    )
    selected_names = [n for n in selected_raw if not n.startswith(DIVIDER_PREFIX)]
    selected_ids = [(all_name_to_id[n], n) for n in selected_names if n in all_name_to_id]

    if selected_ids:
        st.caption(f"{len(selected_ids)} selected")

        # Care / Activity actions — no PIN needed
        st.divider()
        _action_options = {
            "Care": {"Ate": "Meal Confirmed", "Hydration": "Hydration Confirmed", "Sunscreen": "Sunscreen Applied", "Headcount": "Headcount Confirmed"},
            "Activity": {"STEM": "STEM Activity Completed", "SEL": "SEL Activity Completed", "PE": "PE Activity Completed", "ARTS": "Arts & Crafts Completed"},
        }
        cat_col, act_col, btn_col = st.columns([0.25, 0.45, 0.3])
        with cat_col:
            category = st.radio("Type", list(_action_options.keys()), key="bulk_cat", label_visibility="collapsed")
        with act_col:
            action_dict = _action_options[category]
            selected_action = st.selectbox("Action", list(action_dict.keys()), key="bulk_act", label_visibility="collapsed")
        with btn_col:
            if st.button(f"Log {selected_action}", width="stretch"):
                ts = now_timestamp()
                for _, child_name in selected_ids:
                    logs_ref.push({"timestamp": ts, "action": selected_action, "staff": staff, "child": child_name, "notes": action_dict[selected_action]})
                st.toast(f"{selected_action} logged for {len(selected_ids)} children")
                rerun()

        # Sign out / Move — PIN required
        st.divider()
        bulk_pin = st.text_input("PIN for sign out / move:", type="password", key="bulk_pin")
        col_out, col_move = st.columns(2)
        with col_out:
            if st.button("✅ Sign Out", width="stretch"):
                if bulk_pin == CHECKOUT_PIN and bulk_pin:
                    for child_id, child_name in selected_ids:
                        assignments_ref.child(child_id).delete()
                        logs_ref.push({"timestamp": now_timestamp(), "action": "Checkout", "staff": staff, "child": child_name, "notes": "Child Checked Out"})
                    st.success(f"Signed out {len(selected_ids)} {'child' if len(selected_ids) == 1 else 'children'}.")
                    rerun()
                else:
                    st.error("Incorrect PIN.")
        with col_move:
            move_to = st.selectbox("Move to:", [s for s in STAFF if s], key="bulk_move_to")
            if st.button("🔄 Move", width="stretch"):
                if bulk_pin == CHECKOUT_PIN and bulk_pin:
                    for child_id, child_name in selected_ids:
                        assignments_ref.child(child_id).update({"staff": move_to, "child": child_name})
                        logs_ref.push({"timestamp": now_timestamp(), "action": "Move", "staff": move_to, "child": child_name, "notes": f"Bulk moved to {move_to}"})
                    st.success(f"Moved {len(selected_ids)} {'child' if len(selected_ids) == 1 else 'children'} to {move_to}.")
                    rerun()
                else:
                    st.error("Incorrect PIN.")

    st.subheader("➕ Add Child")
    new_child = st.text_input("Name(s) — separate multiple with commas:", key="new_child_global")
    if st.button("Add Child"):
        names = [n.strip() for n in new_child.split(",") if n.strip()]
        for name in names:
            assignments_ref.push({"staff": staff, "child": name})
            logs_ref.push({
                "timestamp": now_timestamp(),
                "action": "Add",
                "staff": staff,
                "child": name,
                "notes": "Added"
            })
        if names:
            st.success(f"Added {len(names)} child{'ren' if len(names) != 1 else ''}.")
            rerun()

    st.subheader("Children", divider="gray")
    st.write(f"🏕️ Total in Center: **{len(data)}**")
    st.write(f"🧑‍🏫 Under {staff}: **{len(rows_with_index)}**")


    for i, row in enumerate(rows_with_index):
        child_name = row["child"]
        child_id = row["id"]
        in_bathroom = row.get("bathroom", False)

        label = f"🚻 {child_name}" if in_bathroom else child_name
        with st.expander(label):
            st.caption(f"📍 {new_location}")

            c1, c2 = st.columns(2)
            with c1:
                if in_bathroom:
                    if st.button("✅ Back", key=f"bath_{i}", width="stretch"):
                        assignments_ref.child(child_id).update({"bathroom": False})
                        logs_ref.push({"timestamp": now_timestamp(), "action": "BATHROOM_RETURN", "staff": staff, "child": child_name, "notes": "Returned from bathroom"})
                        rerun()
                else:
                    if st.button("🚻 Bathroom", key=f"bath_{i}", width="stretch"):
                        assignments_ref.child(child_id).update({"bathroom": True})
                        logs_ref.push({"timestamp": now_timestamp(), "action": "BATHROOM", "staff": staff, "child": child_name, "notes": "Bathroom Break"})
                        rerun()
            with c2:
                new_staff_for_child = st.selectbox("Move to:", [s for s in STAFF if s], index=STAFF.index(staff) if staff in STAFF else 0, key=f"move_{i}", label_visibility="collapsed")
                if st.button("🔄 Move", key=f"btn_move_{i}", width="stretch"):
                    assignments_ref.child(child_id).update({"staff": new_staff_for_child, "child": child_name})
                    logs_ref.push({"timestamp": now_timestamp(), "action": "Move", "staff": new_staff_for_child, "child": child_name, "notes": f"Moved from {staff} to {new_staff_for_child}"})
                    st.success(f"Moved to {new_staff_for_child}")
                    rerun()

            inc_col, btn_col = st.columns([0.78, 0.22])
            with inc_col:
                incident_note = st.text_input("Incident note", placeholder="Describe incident…", key=f"inc_{i}", label_visibility="collapsed")
            with btn_col:
                if st.button("Log", key=f"btn_inc_{i}", width="stretch"):
                    if incident_note:
                        incidents_ref.push({"timestamp": now_timestamp(), "staff": staff, "child": child_name, "note": incident_note})
                        st.toast("Incident logged")
                        rerun()
                    else:
                        st.warning("Enter a note first.")

    # --- OTHER STAFF AT THIS CENTER ---
    other_staff = [s for s in STAFF if s and s != staff]
    if other_staff:
        st.divider()
        with st.expander(f"👥 Rest of Center ({len(data) - len(rows_with_index)} children)", expanded=False):
          for other in other_staff:
            other_loc = staff_lookup.get(other, "N/A")
            other_rows = data[data["staff"] == other].to_dict(orient="records")
            st.markdown(f"**{other}** — {len(other_rows)} children")
            for j, orow in enumerate(other_rows):
                ochild = orow["child"]
                ochild_id = orow["id"]
                oin_bathroom = orow.get("bathroom", False)
                olabel = f"🚻 {ochild}" if oin_bathroom else ochild
                with st.expander(olabel):
                    st.caption(f"📍 {other_loc}")
                    c1, c2 = st.columns(2)
                    with c1:
                        if oin_bathroom:
                            if st.button("✅ Back", key=f"obath_{other}_{j}", width="stretch"):
                                assignments_ref.child(ochild_id).update({"bathroom": False})
                                logs_ref.push({"timestamp": now_timestamp(), "action": "BATHROOM_RETURN", "staff": other, "child": ochild, "notes": "Returned from bathroom"})
                                rerun()
                        else:
                            if st.button("🚻 Bathroom", key=f"obath_{other}_{j}", width="stretch"):
                                assignments_ref.child(ochild_id).update({"bathroom": True})
                                logs_ref.push({"timestamp": now_timestamp(), "action": "BATHROOM", "staff": other, "child": ochild, "notes": "Bathroom Break"})
                                rerun()
                    with c2:
                        omove_to = st.selectbox("Move to:", [s for s in STAFF if s], index=STAFF.index(other) if other in STAFF else 0, key=f"omove_{other}_{j}", label_visibility="collapsed")
                        if st.button("🔄 Move", key=f"obtn_move_{other}_{j}", width="stretch"):
                            assignments_ref.child(ochild_id).update({"staff": omove_to, "child": ochild})
                            logs_ref.push({"timestamp": now_timestamp(), "action": "Move", "staff": omove_to, "child": ochild, "notes": f"Moved from {other} to {omove_to}"})
                            st.success(f"Moved to {omove_to}")
                            rerun()
                    oinc_col, obtn_col = st.columns([0.78, 0.22])
                    with oinc_col:
                        oinc = st.text_input("Incident note", placeholder="Describe incident…", key=f"oinc_{other}_{j}", label_visibility="collapsed")
                    with obtn_col:
                        if st.button("Log", key=f"obtn_inc_{other}_{j}", width="stretch"):
                            if oinc:
                                incidents_ref.push({"timestamp": now_timestamp(), "staff": other, "child": ochild, "note": oinc})
                                st.toast("Incident logged")
                                rerun()
                            else:
                                st.warning("Enter a note first.")
            if not other_rows:
                st.caption("No children assigned")


# ADMIN VIEW
if page == "📊 Admin View":
    pin_input = st.text_input("🔐 Enter Admin PIN:", type="password", max_chars=4)
    if pin_input != ADMIN_PIN:
        if pin_input:
            st.error("Incorrect PIN.")
        st.stop()

    # Load data
    staff_data = fetch_staff()
    assignments_data = fetch_assignments()
    logs_data = safe_get(logs_ref)
    incidents_data = safe_get(incidents_ref)
    memos_data = fetch_memos()
    
    # Build staff lookup
    staff_lookup = {v["name"]: v.get("location", "N/A") for v in staff_data.values()}
    STAFF = list(staff_lookup.keys())

    # Emergency Actions Section
    st.header("🚨 Emergency Actions", divider="red")
    
    # Remove All Children Feature with Double Confirmation
    if "confirm_remove_all_1" not in st.session_state:
        st.session_state.confirm_remove_all_1 = False
    if "confirm_remove_all_2" not in st.session_state:
        st.session_state.confirm_remove_all_2 = False

    with st.expander("⚠️ Remove All Children", expanded=False):
        st.warning("This action will remove ALL children from the system. Use with extreme caution!")
        
        if not st.session_state.confirm_remove_all_1:
            if st.button("Remove All Children"):
                st.session_state.confirm_remove_all_1 = True
        elif not st.session_state.confirm_remove_all_2:
            st.error("Are you absolutely sure? This cannot be undone!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Yes, I'm Sure"):
                    st.session_state.confirm_remove_all_2 = True
            with col2:
                if st.button("Cancel"):
                    st.session_state.confirm_remove_all_1 = False
        else:
            st.error("Final Warning! All children will be removed!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Confirm Final Action"):
                    # Remove all children
                    assignments_ref.delete()
                    logs_ref.push({
                        "timestamp": now_timestamp(),
                        "action": "SYSTEM",
                        "staff": "ADMIN",
                        "child": "ALL",
                        "notes": "All children removed from system"
                    })
                    st.session_state.confirm_remove_all_1 = False
                    st.session_state.confirm_remove_all_2 = False
                    st.success("✅ All children have been removed")
                    rerun()
            with col2:
                if st.button("Cancel Action"):
                    st.session_state.confirm_remove_all_1 = False
                    st.session_state.confirm_remove_all_2 = False
    
    # Assignments Section
    st.header("👥 Active Assignments", divider="gray")
    
    assignment_rows = []
    for k, v in assignments_data.items():
        assignment_rows.append({
            "id": k,
            "staff": v.get("staff", ""),
            "child": v.get("child", "")
        })
    
    assignments_df = pd.DataFrame(assignment_rows)
    
    if assignments_df.empty:
        st.success("✅ No active assignments.")
    else:
        assignments_grouped = assignments_df.groupby("staff").size().reset_index(name="Child Count")
    
        with st.expander("📊 Children Count Per Staff", expanded=True):
            st.dataframe(assignments_grouped, width="stretch")
    
        st.divider()
    
        st.subheader("📋 Full Staff Rosters")
    
        for staff_member in STAFF:
            assigned_children = assignments_df[assignments_df["staff"] == staff_member]
            location = staff_lookup.get(staff_member, "N/A")
            child_count = len(assigned_children)
    
            st.markdown(f"#### 👤 {staff_member} — Location: {location} — `{child_count} kids`")
    
            if not assigned_children.empty:
                st.table(assigned_children[["child"]].reset_index(drop=True))
            else:
                st.write("No children assigned.")
    
    st.divider()
    
    # Logs Section with Date Filtering
    st.header("📊 Logs Summary", divider="gray")
    
    log_rows = []
    for k, v in logs_data.items():
        log_rows.append([
            v.get("timestamp", ""),
            v.get("action", ""),
            v.get("staff", ""),
            v.get("child", ""),
            v.get("notes", "")
        ])
    
    logs_df = pd.DataFrame(log_rows, columns=["timestamp", "action", "staff", "child", "notes"])
    
    if logs_df.empty:
        st.success("✅ No logs found.")
    else:
        logs_df["parsed_timestamp"] = pd.to_datetime(logs_df["timestamp"], format="%B %d, %Y %I:%M %p", errors="coerce")
        logs_df = logs_df.sort_values(by="parsed_timestamp", ascending=False)

        # Date Filter
        col1, col2 = st.columns([1, 2])
        with col1:
            selected_date = st.date_input("Filter by Date:", datetime.datetime.now(MT).date())
        
        # Filter logs by selected date
        date_filtered_logs = logs_df[logs_df["parsed_timestamp"].dt.date == selected_date]
        
        with st.expander("📄 Today's Logs", expanded=True):
            if date_filtered_logs.empty:
                st.info(f"No logs found for {selected_date}")
            else:
                st.dataframe(
                    date_filtered_logs.drop(columns=["parsed_timestamp"]),
                    width="stretch",
                    height=300
                )

        # Child-specific log view
        st.subheader("👶 Child-Specific Logs", divider="gray")
        
        # Get unique children from both assignments and logs
        all_children = set()
        if not assignments_df.empty:
            all_children.update(assignments_df["child"].unique())
        all_children.update(logs_df["child"].unique())
        all_children = sorted(list(all_children - {"ALL", "[LOCATION UPDATE]"}))  # Remove system entries
        
        selected_child = st.selectbox("Select Child:", [""] + all_children)
        
        if selected_child:
            child_logs = logs_df[logs_df["child"] == selected_child].sort_values(by="parsed_timestamp", ascending=False)
            
            if child_logs.empty:
                st.info(f"No logs found for {selected_child}")
            else:
                # Summary statistics
                total_logs = len(child_logs)
                unique_actions = child_logs["action"].nunique()
                staff_interactions = child_logs["staff"].nunique()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Logs", total_logs)
                with col2:
                    st.metric("Unique Actions", unique_actions)
                with col3:
                    st.metric("Staff Interactions", staff_interactions)
                
                # Display detailed logs
                st.markdown("#### Detailed Log History")
                for _, row in child_logs.iterrows():
                    with st.expander(f"🕒 {row['timestamp']} - {row['action']}", expanded=False):
                        st.write(f"**Staff:** {row['staff']}")
                        st.write(f"**Action:** {row['action']}")
                        st.write(f"**Notes:** {row['notes']}")
    
        log_counts = logs_df["staff"].value_counts().reset_index()
        log_counts.columns = ["staff", "log_count"]
    
        with st.expander("📈 Log Counts Per Staff", expanded=False):
            st.dataframe(log_counts, width="stretch")
    
    st.divider()
    
    # Incidents Section
    st.header("🚨 Incidents Summary", divider="gray")
    
    incident_rows = []
    for k, v in incidents_data.items():
        incident_rows.append([
            v.get("timestamp", ""),
            v.get("staff", ""),
            v.get("child", ""),
            v.get("note", "")
        ])
    
    incidents_df = pd.DataFrame(incident_rows, columns=["timestamp", "staff", "child", "note"])
    
    if incidents_df.empty:
        st.success("✅ No incidents found.")
    else:
        incidents_df["parsed_timestamp"] = pd.to_datetime(incidents_df["timestamp"], format="%B %d, %Y %I:%M %p", errors="coerce")
        incidents_df = incidents_df.sort_values(by="parsed_timestamp", ascending=False)
    
        st.dataframe(
            incidents_df.drop(columns=["parsed_timestamp"]),
            width="stretch",
            height=400
        )

    st.divider()

    # Staff Management
    st.header("👤 Staff Management", divider="gray")
    col_add, col_remove = st.columns(2)

    with col_add:
        st.subheader("➕ Add Staff")
        new_staff_name = st.text_input("Name:")
        new_staff_location = st.text_input("Location:")
        if st.button("Add Staff Member"):
            if new_staff_name.strip():
                staff_ref.push({"name": new_staff_name.strip(), "location": new_staff_location.strip() or "N/A"})
                st.success(f"Added {new_staff_name}")
                rerun()

    with col_remove:
        st.subheader("➖ Remove Staff")
        remove_name = st.selectbox("Select:", [""] + [s for s in STAFF if s], key="admin_remove_staff")
        if remove_name:
            if st.button(f"Remove {remove_name}"):
                st.session_state["confirm_remove_staff"] = remove_name
        if st.session_state.get("confirm_remove_staff") == remove_name and remove_name:
            st.warning(f"Remove {remove_name}?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes, Remove", key="rm_staff_yes"):
                    for key, value in staff_data_raw.items():
                        if value.get("name") == remove_name:
                            staff_ref.child(key).delete()
                            break
                    logs_ref.push({
                        "timestamp": now_timestamp(),
                        "action": "SYSTEM",
                        "staff": "ADMIN",
                        "child": "[STAFF REMOVED]",
                        "notes": f"Removed staff member: {remove_name}"
                    })
                    del st.session_state["confirm_remove_staff"]
                    st.success(f"Removed {remove_name}")
                    rerun()
            with c2:
                if st.button("Cancel", key="rm_staff_no"):
                    del st.session_state["confirm_remove_staff"]

    st.divider()

    # Health Report
    st.header("🏥 Health Report", divider="gray")
    uploaded_file = st.file_uploader("📂 Upload Rosters Export CSV", type=["csv"])
    if uploaded_file is not None:
        df_csv = pd.read_csv(uploaded_file)
        con = duckdb.connect(database=':memory:')
        con.register("roster", df_csv)
        csv_cols = set(df_csv.columns.tolist())

        def col_expr(candidates, alias):
            match = next((c for c in candidates if c in csv_cols), None)
            return f'"{match}" AS {alias}' if match else f"NULL AS {alias}"

        select_parts = [
            col_expr(["Participant"], "Participant"),
            col_expr(["allergies-sensitivities-details"], "Allergies"),
            col_expr(["illness-medical-conditions-details"], "MedicalConditions"),
            col_expr(["behavior-mental-health-info", "behavior-mental-health-details"], "MentalHealthInfo"),
            col_expr(["additional-health-info-or-special-instructions"], "HealthInfo"),
            col_expr(["current-regular-medications", "list-regular-medications"], "Medications"),
            col_expr(["Unit Primary Phone"], "PrimaryPhone"),
            col_expr(["Emergency Phone"], "EmergencyPhone"),
        ]
        query = f"SELECT {', '.join(select_parts)} FROM roster"
        try:
            df_health = con.execute(query).df()
        except Exception as e:
            st.error(f"Query failed: {e}")
            st.write("**Columns in your CSV:**", list(csv_cols))
            st.stop()
        df_health.columns = [c.replace("-", " ").replace("/", " ").title() for c in df_health.columns]
        df_health = df_health.sort_values("Participant", key=lambda s: s.str.split().str[0].str.lower()).reset_index(drop=True)
        html_table = df_health.to_html(index=False, justify="center", border=1, escape=False)
        full_html = f"<html><body><h2>YMCA Health & Emergency Summary</h2>{html_table}</body></html>"
        st.success("✅ Report generated!")
        st.download_button("📥 Download HTML Report", full_html.encode("utf-8"), "health_report.html", "text/html")
    else:
        st.info("Upload a Rosters Export CSV to generate the health report.")

    st.divider()

    if site == "cfc":
        # Memo Editing
        st.header("📝 Memo Editor", divider="gray")

        memo_edit_date = st.date_input("Date", datetime.datetime.now(MT).date(), key="admin_memo_date")
        memos_data_admin = fetch_memos()

        master_memo_id, master_memo_text = None, ""
        for k, v in memos_data_admin.items():
            if v.get("staff") == "Hunter" and v.get("date") == memo_edit_date.isoformat():
                master_memo_id, master_memo_text = k, v.get("memo", "")
                break

        col1, col2 = st.columns(2)
        with col1:
            edited_memo = st.text_area("Memo Content:", value=master_memo_text, height=500, key=f"admin_memo_text_{memo_edit_date.isoformat()}")

            if st.button("💾 Save & Push to All Staff"):
                safe_memo = edited_memo.replace("\r\n", "\n")
                for staff_member in [s for s in STAFF if s]:
                    existing_key = next(
                        (k for k, v in memos_data_admin.items()
                         if v.get("staff") == staff_member and v.get("date") == memo_edit_date.isoformat()),
                        None
                    )
                    payload = {"staff": staff_member, "date": memo_edit_date.isoformat(), "memo": safe_memo}
                    (memos_ref.child(existing_key).update if existing_key else memos_ref.push)(payload)
                st.success(f"✅ Memo pushed to all staff for {memo_edit_date}")
                rerun()

            if master_memo_id and st.button("🗑️ Delete Memo for All Staff"):
                for k, v in memos_data_admin.items():
                    if v.get("date") == memo_edit_date.isoformat():
                        memos_ref.child(k).delete()
                st.success("✅ Memo deleted for all staff")
                rerun()

        with col2:
            st.markdown("### Preview:")
            st.markdown(edited_memo or "*No content yet...*", unsafe_allow_html=True)

        st.divider()

        # PDF File Manager
        st.header("📁 File Manager", divider="gray")

        BUCKET_NAME = "group-manager-a55a2.firebasestorage.app"

        def _upload_files(uploaded, folder, label, db_ref, extra_fields=None):
            bucket = storage.bucket(BUCKET_NAME)
            for f in uploaded:
                path = f"{folder}/{f.name}"
                blob = bucket.blob(path)
                download_token = str(uuid.uuid4())
                blob.metadata = {"firebaseStorageDownloadTokens": download_token}
                f.seek(0)
                blob.upload_from_file(f, content_type="application/pdf")
                blob.patch()
                encoded_path = urllib.parse.quote(path, safe="")
                url = (
                    f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}"
                    f"/o/{encoded_path}?alt=media&token={download_token}"
                )
                record = {"label": label, "name": f.name, "url": url}
                if extra_fields:
                    record.update(extra_fields)
                db_ref.push(record)

        fm_tab1, fm_tab2, fm_tab3 = st.tabs(["📅 Camp Day Files", "📋 SOPs", "🎓 Training"])

        with fm_tab1:
            upload_date = st.date_input("Date these files belong to:", datetime.datetime.now(MT).date(), key="upload_date")
            upload_label = st.text_input("Label / Session (e.g. Week 1 — Extreme Earth):", key="upload_label")
            uploaded_pdfs = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True, key="pdf_uploader")

            if uploaded_pdfs and st.button("⬆️ Upload Files", key="btn_upload_camp"):
                _upload_files(
                    uploaded_pdfs,
                    folder=f"camp/{upload_date.isoformat()}",
                    label=upload_label.strip() or upload_date.isoformat(),
                    db_ref=files_ref,
                    extra_fields={"date": upload_date.isoformat(), "type": "pdf"},
                )
                st.cache_data.clear()
                st.success(f"✅ {len(uploaded_pdfs)} file(s) uploaded")
                rerun()

            st.divider()
            st.markdown("**🔗 Add a Link**")
            lc1, lc2 = st.columns(2)
            with lc1:
                link_title = st.text_input("Link title:", key="camp_link_title")
                link_url = st.text_input("URL:", key="camp_link_url")
            with lc2:
                link_date = st.date_input("Date:", datetime.datetime.now(MT).date(), key="camp_link_date")
                link_label = st.text_input("Label / Session:", key="camp_link_label")
            if st.button("➕ Add Link", key="btn_add_camp_link"):
                if link_title.strip() and link_url.strip():
                    files_ref.push({
                        "date": link_date.isoformat(),
                        "label": link_label.strip() or link_date.isoformat(),
                        "name": link_title.strip(),
                        "url": link_url.strip(),
                        "type": "link",
                    })
                    st.cache_data.clear()
                    st.success(f"✅ Link '{link_title.strip()}' added")
                    rerun()
                else:
                    st.error("Enter both a title and URL.")

            all_files = fetch_files()
            if all_files:
                st.subheader("Uploaded Files")
                files_by_date = {}
                for k, v in all_files.items():
                    d = v.get("date", "Unknown")
                    files_by_date.setdefault(d, []).append({**v, "key": k})
                for d in sorted(files_by_date.keys(), reverse=True):
                    with st.expander(f"📅 {d} — {files_by_date[d][0].get('label', '')}"):
                        for f in files_by_date[d]:
                            col_a, col_b = st.columns([4, 1])
                            with col_a:
                                icon = "🔗" if f.get("type") == "link" else "📄"
                                st.markdown(f"{icon} [{f['name']}]({f['url']})")
                            with col_b:
                                if st.button("🗑️", key=f"del_{f['key']}"):
                                    if f.get("type") != "link":
                                        storage.bucket(BUCKET_NAME).blob(f"camp/{d}/{f['name']}").delete()
                                    files_ref.child(f["key"]).delete()
                                    st.cache_data.clear()
                                    rerun()

        with fm_tab2:
            sop_label = st.text_input("Category / Label (e.g. Emergency Procedures, Health Protocols):", key="sop_label")
            uploaded_sops = st.file_uploader("Upload SOP PDFs", type=["pdf"], accept_multiple_files=True, key="sop_uploader")
            if uploaded_sops and st.button("⬆️ Upload SOPs", key="btn_upload_sop"):
                if not sop_label.strip():
                    st.error("Please enter a label/category before uploading.")
                else:
                    _upload_files(uploaded_sops, folder=f"sop/{sop_label.strip()}", label=sop_label.strip(), db_ref=sop_ref, extra_fields={"type": "pdf"})
                    st.cache_data.clear()
                    st.success(f"✅ {len(uploaded_sops)} SOP(s) uploaded under '{sop_label.strip()}'")
                    rerun()

            st.divider()
            st.markdown("**🔗 Add a Link**")
            sl1, sl2 = st.columns(2)
            with sl1:
                sop_link_title = st.text_input("Link title:", key="sop_link_title")
                sop_link_url = st.text_input("URL:", key="sop_link_url")
            with sl2:
                sop_link_label = st.text_input("Category / Label:", key="sop_link_label")
            if st.button("➕ Add Link", key="btn_add_sop_link"):
                if sop_link_title.strip() and sop_link_url.strip() and sop_link_label.strip():
                    sop_ref.push({"label": sop_link_label.strip(), "name": sop_link_title.strip(), "url": sop_link_url.strip(), "type": "link"})
                    st.cache_data.clear()
                    st.success(f"✅ Link '{sop_link_title.strip()}' added")
                    rerun()
                else:
                    st.error("Enter title, URL, and category.")

            all_sops = fetch_sop_files()
            if all_sops:
                st.subheader("SOP Files")
                sops_by_label = {}
                for k, v in all_sops.items():
                    lbl = v.get("label", "Uncategorized")
                    sops_by_label.setdefault(lbl, []).append({**v, "key": k})
                for lbl in sorted(sops_by_label.keys()):
                    with st.expander(f"📋 {lbl}"):
                        for f in sops_by_label[lbl]:
                            col_a, col_b = st.columns([4, 1])
                            with col_a:
                                icon = "🔗" if f.get("type") == "link" else "📄"
                                st.markdown(f"{icon} [{f['name']}]({f['url']})")
                            with col_b:
                                if st.button("🗑️", key=f"del_sop_{f['key']}"):
                                    if f.get("type") != "link":
                                        storage.bucket(BUCKET_NAME).blob(f"sop/{lbl}/{f['name']}").delete()
                                    sop_ref.child(f["key"]).delete()
                                    st.cache_data.clear()
                                    rerun()

        with fm_tab3:
            training_label = st.text_input("Category / Label (e.g. CPR, Mandated Reporter, Orientation):", key="training_label")
            uploaded_training = st.file_uploader("Upload Training PDFs", type=["pdf"], accept_multiple_files=True, key="training_uploader")
            if uploaded_training and st.button("⬆️ Upload Training Files", key="btn_upload_training"):
                if not training_label.strip():
                    st.error("Please enter a label/category before uploading.")
                else:
                    _upload_files(uploaded_training, folder=f"training/{training_label.strip()}", label=training_label.strip(), db_ref=training_ref, extra_fields={"type": "pdf"})
                    st.cache_data.clear()
                    st.success(f"✅ {len(uploaded_training)} file(s) uploaded under '{training_label.strip()}'")
                    rerun()

            st.divider()
            st.markdown("**🔗 Add a Link**")
            tl1, tl2 = st.columns(2)
            with tl1:
                tr_link_title = st.text_input("Link title:", key="tr_link_title")
                tr_link_url = st.text_input("URL:", key="tr_link_url")
            with tl2:
                tr_link_label = st.text_input("Category / Label:", key="tr_link_label")
            if st.button("➕ Add Link", key="btn_add_tr_link"):
                if tr_link_title.strip() and tr_link_url.strip() and tr_link_label.strip():
                    training_ref.push({"label": tr_link_label.strip(), "name": tr_link_title.strip(), "url": tr_link_url.strip(), "type": "link"})
                    st.cache_data.clear()
                    st.success(f"✅ Link '{tr_link_title.strip()}' added")
                    rerun()
                else:
                    st.error("Enter title, URL, and category.")

            all_training = fetch_training_files()
            if all_training:
                st.subheader("Training Files")
                training_by_label = {}
                for k, v in all_training.items():
                    lbl = v.get("label", "Uncategorized")
                    training_by_label.setdefault(lbl, []).append({**v, "key": k})
                for lbl in sorted(training_by_label.keys()):
                    with st.expander(f"🎓 {lbl}"):
                        for f in training_by_label[lbl]:
                            col_a, col_b = st.columns([4, 1])
                            with col_a:
                                icon = "🔗" if f.get("type") == "link" else "📄"
                                st.markdown(f"{icon} [{f['name']}]({f['url']})")
                            with col_b:
                                if st.button("🗑️", key=f"del_training_{f['key']}"):
                                    if f.get("type") != "link":
                                        storage.bucket(BUCKET_NAME).blob(f"training/{lbl}/{f['name']}").delete()
                                    training_ref.child(f["key"]).delete()
                                    st.cache_data.clear()
                                    rerun()


# MY MEMOS
if page == "📅 My Memos" and site == "cfc":
    st.title("📅 My Memos")

    memos_data = fetch_memos()
    today = datetime.datetime.now(MT).date()

    upcoming = []
    for k, v in memos_data.items():
        if v.get("staff") == "Hunter" and v.get("memo", "").strip():
            try:
                d = datetime.date.fromisoformat(v.get("date", ""))
                if d >= today:
                    upcoming.append((d, v.get("memo", "")))
            except ValueError:
                pass

    upcoming.sort(key=lambda x: x[0])

    if not upcoming:
        st.info("No upcoming memos found.")
    else:
        dates = [str(d) for d, _ in upcoming]
        if "memo_date_idx" not in st.session_state:
            st.session_state["memo_date_idx"] = 0
        idx = min(st.session_state["memo_date_idx"], len(dates) - 1)

        prev_col, date_col, next_col = st.columns([0.2, 0.6, 0.2])
        with prev_col:
            if st.button("◀", width="stretch", disabled=idx == 0):
                st.session_state["memo_date_idx"] = idx - 1
                rerun()
        with date_col:
            st.markdown(f"<div style='text-align:center;font-weight:600;padding-top:0.4rem'>{dates[idx]}</div>", unsafe_allow_html=True)
        with next_col:
            if st.button("▶", width="stretch", disabled=idx == len(dates) - 1):
                st.session_state["memo_date_idx"] = idx + 1
                rerun()

        memo_for_date = upcoming[idx][1]
        st.divider()
        st.markdown(memo_for_date, unsafe_allow_html=True)


# RESOURCES
if page == "📁 Resources" and site == "cfc":
    st.title("📁 Resources")

    st.markdown("""
**📌 Quick Links**

| | |
|---|---|
| 📅 [Schedule](https://ymcautah-my.sharepoint.com/:x:/g/personal/ogdensdc_ymcautah_org/IQByJGGJCK_fSJJASjFWOXC0AcF8b59Wuvr9L3sPwFfP9eg?e=0EODmQ) | 💡 [Idea Doc](https://ymcautah-my.sharepoint.com/:w:/g/personal/ogdensdc_ymcautah_org/IQAN4olqityHSanetqZgxDrEAVhnkpqTr-udpzG87T7OClA?e=7Z4qQk) |
| 🏊 [Swim Tracker](https://docs.google.com/spreadsheets/d/1pQEpvi00oGWXgbLk5i_176ISpCMDfox2Ux3Qk6Lud14/edit?gid=0#gid=0) | 📋 [Admin Planning Doc](https://ymcautah-my.sharepoint.com/:w:/g/personal/ogdensdc_ymcautah_org/IQCINpwiKU4ESK2KXszWW5r0AaA8Wx0mD6dBcd5hw1f4J6Y?e=xg8fdJ) |
| 📤 [Social Media Uploads](https://ymcautah.sharepoint.com/:f:/s/Administration/IgC4Gyac5TJyT5r2-mrsUEGNAQW6-f4NUtoOPO3owtfqX0o?e=qc6a6I) | |
""")

    st.divider()

    res_tab1, res_tab2, res_tab3 = st.tabs(["📅 Camp Day Files", "📋 SOPs", "🎓 Training"])

    with res_tab1:
        all_files = fetch_files()
        if not all_files:
            st.info("No camp day files uploaded yet.")
        else:
            today = datetime.datetime.now(MT).date()
            files_by_date = {}
            for k, v in all_files.items():
                try:
                    d = datetime.date.fromisoformat(v.get("date", ""))
                except ValueError:
                    continue
                files_by_date.setdefault(d, []).append(v)

            def _render_file(f):
                icon = "🔗" if f.get("type") == "link" else "📄"
                st.markdown(f"{icon} [{f['name']}]({f['url']})")

            past = {d: f for d, f in files_by_date.items() if d < today}
            upcoming = {d: f for d, f in files_by_date.items() if d >= today}

            if upcoming:
                st.subheader("📅 Upcoming")
                # Group by ISO week
                weeks = {}
                for d in sorted(upcoming.keys()):
                    iso_year, iso_week, _ = d.isocalendar()
                    week_key = (iso_year, iso_week)
                    weeks.setdefault(week_key, []).append(d)
                for (iso_year, iso_week), days in sorted(weeks.items()):
                    week_start = days[0]
                    week_end = days[-1]
                    week_label = f"Week of {week_start.strftime('%b %-d')}–{week_end.strftime('%-d')}" if week_start != week_end else f"Week of {week_start.strftime('%b %-d')}"
                    with st.expander(f"📆 {week_label}", expanded=(iso_year, iso_week) == today.isocalendar()[:2]):
                        for d in sorted(days):
                            day_label = upcoming[d][0].get("label", str(d))
                            st.markdown(f"**{d.strftime('%A, %b %-d')} — {day_label}**")
                            for f in upcoming[d]:
                                _render_file(f)

            if past:
                st.subheader("🗂️ Past")
                for d in sorted(past.keys(), reverse=True):
                    label = past[d][0].get("label", str(d))
                    with st.expander(f"{d} — {label}"):
                        for f in past[d]:
                            _render_file(f)

    with res_tab2:
        st.markdown("""
<div style="background:#1e3a5f;border-radius:10px;padding:1rem 1.25rem;margin-bottom:1rem">
<div style="font-size:1.05rem;font-weight:700;margin-bottom:0.3rem;color:#ffffff">📋 CFC Standard Operating Procedures</div>
<a href="https://ymcautah-my.sharepoint.com/:w:/g/personal/ogdensdc_ymcautah_org/IQBMK-jwK2PDSrNHtmOCeCneAbCKRV-UQVnCxNPd780TdmI?e=u2IqrB" target="_blank" style="color:#7eb8f7;font-weight:600;font-size:0.95rem">📄 Open SOP Document →</a>
</div>
""", unsafe_allow_html=True)

        all_sops = fetch_sop_files()
        if not all_sops:
            st.info("No additional SOP files uploaded yet.")
        else:
            sops_by_label = {}
            for k, v in all_sops.items():
                lbl = v.get("label", "Uncategorized")
                sops_by_label.setdefault(lbl, []).append(v)
            for lbl in sorted(sops_by_label.keys()):
                with st.expander(f"📋 {lbl}"):
                    for f in sops_by_label[lbl]:
                        icon = "🔗" if f.get("type") == "link" else "📄"
                        st.markdown(f"{icon} [{f['name']}]({f['url']})")

    with res_tab3:
        all_training = fetch_training_files()
        if not all_training:
            st.info("No training files uploaded yet.")
        else:
            training_by_label = {}
            for k, v in all_training.items():
                lbl = v.get("label", "Uncategorized")
                training_by_label.setdefault(lbl, []).append(v)
            for lbl in sorted(training_by_label.keys()):
                with st.expander(f"🎓 {lbl}"):
                    for f in training_by_label[lbl]:
                        icon = "🔗" if f.get("type") == "link" else "📄"
                        st.markdown(f"{icon} [{f['name']}]({f['url']})")



# HOW TO USE
if page == "ℹ️ How to Use":
    st.title("ℹ️ How to Use SDC Manager")

    st.markdown("---")

    with st.expander("👩‍🏫 Staff View", expanded=True):
        st.markdown("""
**Your home base.** Select your name at the top to load your group.

- **Location** — Keep this updated at all times so admin can see where your group is.
- **Bulk Actions** — Select children by group or individually to log care actions, sign out, or move as a group. Tap a staff name in the dropdown to load their whole group at once.
- **Add Child** — Type one name or multiple comma-separated names to add children to your group.
- **Children** — Each child is an expander. Tap to open actions:
  - 🚻 **Bathroom** — flags the child with a toilet icon until marked Back
  - 🔄 **Move** — reassign to another staff member
  - **Log** — record an incident note
- **Rest of Center** — collapsed view of all other staff and their children. Tap to expand and take actions on any child.
- **Bulk Actions** — at the bottom. Select children from any group, log care/activity events without a PIN, or sign out / move with PIN `••••`.
""")

    with st.expander("⚡ Bulk Actions detail"):
        st.markdown("""
- Tap **`── Staff Name ──`** in the dropdown to instantly load that staff's children
- Mix and match children from any group
- **Care / Activity** actions (Ate, Hydration, Sunscreen, STEM, etc.) log immediately — no PIN needed
- **Sign Out** and **Move** require the checkout PIN
""")

    with st.expander("📊 Admin View"):
        st.markdown("""
Requires Admin PIN.

- View all staff, assignments, logs, and incidents
- Edit staff roster
- Emergency: remove all children
- Review incident history
""")

    with st.expander("📅 My Memos"):
        st.markdown("""
Daily memos written by the director. Navigate with **◀ ▶** buttons to browse upcoming days.
Memos also appear in the sidebar of Staff View on the day they're active.
""")

    with st.expander("📁 Resources"):
        st.markdown("""
Activity PDFs organized by camp day. Tap a date to expand and download materials for that day.
""")

    with st.expander("🔑 PINs & Access"):
        st.markdown("""
- **Checkout PIN** — required for bulk sign out and bulk move
- **Admin PIN** — required to access Admin View
- Contact your director if you don't have these
""")

    st.divider()
    st.caption("SDC Manager · Built for Ogden SDC · Questions? Contact Hunter")
