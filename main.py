import streamlit as st
import firebase_admin
from firebase_admin import credentials, db, storage
import pandas as pd
import datetime
import duckdb
from pytz import timezone

ADMIN_PIN = st.secrets.get("ADMIN_PIN", "")
CHECKOUT_PIN = st.secrets.get("CHECKOUT_PIN", "")

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
        'storageBucket': 'group-manager-a55a2.appspot.com'
    })

staff_ref = db.reference(f"{site}/staff")
assignments_ref = db.reference(f"{site}/assignments")
logs_ref = db.reference(f"{site}/logs")
incidents_ref = db.reference(f"{site}/incidents")
memos_ref = db.reference(f"{site}/memos")
files_ref = db.reference(f"{site}/files")
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
STAFF.insert(0, "")

# --- LOAD ASSIGNMENTS DATA ---
assignments_raw = fetch_assignments()
rows = []
for k, v in assignments_raw.items():
    rows.append({
        "id": k,
        "staff": v.get("staff", ""),
        "child": v.get("child", "")
    })
data = pd.DataFrame(rows, columns=["id", "staff", "child"])

#test
# --- PAGE NAVIGATION ---
_nav = ["👩‍🏫 Staff View", "📊 Admin View"]
if site == "cfc":
    _nav += ["📅 My Memos", "📁 Resources"]
page = st.sidebar.radio("📂 Navigate", _nav)

# STAFF VIEW
if page == "👩‍🏫 Staff View":
    st.title(f"SDC Dashboard — {SITE_LABEL} 😎")
    staff = st.selectbox("Select Staff", STAFF)
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

    with st.expander("🛠️ Whole Group Actions", expanded=True):
        action_options = {
            "Care Actions": {
                "Ate": "Meal Confirmed",
                "Hydration": "Hydration Confirmed",
                "Sunscreen": "Sunscreen Applied",
                "Accurate Headcount": "Headcount Confirmed"
            },
            "Activity Participation": {
                "STEM": "STEM Activity Completed",
                "SEL": "SEL Activity Completed",
                "PE": "Physical Education Activity Completed",
                "ARTS": "Arts & Crafts Completed"
            }
        }
        category = st.radio("Action Type", list(action_options.keys()), key="cat")
        action_dict = action_options[category]
        selected_action = st.selectbox(f"Select {category[:-1]}", list(action_dict.keys()), key="act")

        if st.button(f"Confirm {category[:-1]}"):
            timestamp = now_timestamp()
            for row in rows_with_index:
                logs_ref.push({
                    "timestamp": timestamp,
                    "action": selected_action,
                    "staff": staff,
                    "child": row["child"],
                    "notes": action_dict[selected_action]
                })
            st.success(f"✅ {selected_action} logged for all")
            rerun()

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


    st.markdown("""
<style>
/* Compact child rows — no extra vertical space, tight gaps */
[data-testid="stHorizontalBlock"]:has([class*="st-key-bulk_chk_"]) {
    margin-bottom: 0.15rem !important;
    align-items: center !important;
}
[data-testid="stHorizontalBlock"]:has([class*="st-key-bulk_chk_"]) [data-testid="column"] {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}
</style>
""", unsafe_allow_html=True)

    for i, row in enumerate(rows_with_index):
        child_name = row["child"]
        child_id = row["id"]

        col_exp, col_chk = st.columns([0.88, 0.12], vertical_alignment="center")
        with col_chk:
            st.checkbox("", key=f"bulk_chk_{i}", label_visibility="collapsed")
        with col_exp:
            with st.expander(child_name):
                st.caption(f"Assigned to: {staff}  |  Location: {new_location}")

                incident_note = st.text_input(f"Incident:", key=f"inc_{i}")
                if st.button(f"Save Incident", key=f"btn_inc_{i}"):
                    incidents_ref.push({
                        "timestamp": now_timestamp(),
                        "staff": staff,
                        "child": child_name,
                        "note": incident_note
                    })
                    st.success("Incident logged!")
                    rerun()

                if st.button(f"Snack ✅", key=f"snack_{i}"):
                    logs_ref.push({
                        "timestamp": now_timestamp(),
                        "action": "SNACK",
                        "staff": staff,
                        "child": child_name,
                        "notes": "Snack Provided"
                    })
                    st.success(f"Snack logged")
                    rerun()

                new_staff_for_child = st.selectbox(
                    "Reassign:",
                    [s for s in STAFF if s],
                    index=STAFF.index(staff) if staff in STAFF else 0,
                    key=f"move_{i}"
                )
                if st.button(f"Confirm Move", key=f"btn_move_{i}"):
                    assignments_ref.child(child_id).update({"staff": new_staff_for_child, "child": child_name})
                    logs_ref.push({
                        "timestamp": now_timestamp(),
                        "action": "Move",
                        "staff": new_staff_for_child,
                        "child": child_name,
                        "notes": f"Moved from {staff} to {new_staff_for_child}"
                    })
                    st.success(f"Moved to {new_staff_for_child}")
                    rerun()

    # Bulk actions — reads checkboxes already rendered inside expanders above
    if rows_with_index:
        st.subheader("⚡ Bulk Actions", divider="gray")
        selected_ids = [
            (row["id"], row["child"])
            for i, row in enumerate(rows_with_index)
            if st.session_state.get(f"bulk_chk_{i}", False)
        ]

        if selected_ids:
            bulk_pin = st.text_input("PIN:", type="password", key="bulk_pin")
            col_out, col_move = st.columns(2)

            with col_out:
                if st.button("✅ Sign Out"):
                    if bulk_pin == CHECKOUT_PIN:
                        for child_id, child_name in selected_ids:
                            assignments_ref.child(child_id).delete()
                            logs_ref.push({
                                "timestamp": now_timestamp(),
                                "action": "Checkout",
                                "staff": staff,
                                "child": child_name,
                                "notes": "Child Checked Out"
                            })
                        st.success(f"Signed out {len(selected_ids)} {'child' if len(selected_ids) == 1 else 'children'}.")
                        rerun()
                    else:
                        st.error("Incorrect PIN.")

            with col_move:
                move_to = st.selectbox("Move to:", [s for s in STAFF if s], key="bulk_move_to")
                if st.button("🔄 Move"):
                    if bulk_pin == CHECKOUT_PIN:
                        for child_id, child_name in selected_ids:
                            assignments_ref.child(child_id).update({"staff": move_to, "child": child_name})
                            logs_ref.push({
                                "timestamp": now_timestamp(),
                                "action": "Move",
                                "staff": move_to,
                                "child": child_name,
                                "notes": f"Bulk moved from {staff} to {move_to}"
                            })
                        st.success(f"Moved {len(selected_ids)} {'child' if len(selected_ids) == 1 else 'children'} to {move_to}.")
                        rerun()
                    else:
                        st.error("Incorrect PIN.")

    # --- OTHER STAFF AT THIS CENTER ---
    other_staff = [s for s in STAFF if s and s != staff]
    if other_staff:
        st.divider()
        st.subheader("👥 Rest of Center", divider="gray")
        for other in other_staff:
            other_rows = data[data["staff"] == other].to_dict(orient="records")
            st.markdown(f"**{other}** — {len(other_rows)} children")
            if other_rows:
                for row in other_rows:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;• {row['child']}")
            else:
                st.caption("No children assigned")

    with st.expander("🔄 Shift Change - Bulk Move"):
        col1, col2 = st.columns(2)
        with col1:
            from_staff = st.selectbox("From Staff", [s for s in STAFF if s], key="from_swap")
        with col2:
            to_staff = st.selectbox("To Staff", [s for s in STAFF if s], key="to_swap")

        if st.button("Swap Roles"):
            count = 0
            staff_assignments = data[data["staff"] == from_staff]
            for _, row in staff_assignments.iterrows():
                assignments_ref.child(row["id"]).update({
                    "staff": to_staff,
                    "child": row["child"]
                })
                logs_ref.push({
                    "timestamp": now_timestamp(),
                    "action": "Role Swap",
                    "staff": to_staff,
                    "child": row["child"],
                    "notes": f"Moved from {from_staff} to {to_staff}"
                })
                count += 1
            st.success(f"Moved {count} children.")
            rerun()



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
            st.dataframe(assignments_grouped, use_container_width=True)
    
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
                    use_container_width=True,
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
            st.dataframe(log_counts, use_container_width=True)
    
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
            use_container_width=True,
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
            col_expr(["list-regular-medications"], "Medications"),
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
            edited_memo = st.text_area("Memo Content:", value=master_memo_text, height=500, key="admin_memo_text")

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

        upload_date = st.date_input("Date these files belong to:", datetime.datetime.now(MT).date(), key="upload_date")
        upload_label = st.text_input("Label / Session (e.g. Week 1 — Extreme Earth):", key="upload_label")
        uploaded_pdfs = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True, key="pdf_uploader")

        if uploaded_pdfs and st.button("⬆️ Upload Files"):
            bucket = storage.bucket()
            for f in uploaded_pdfs:
                path = f"camp/{upload_date.isoformat()}/{f.name}"
                blob = bucket.blob(path)
                blob.upload_from_file(f, content_type="application/pdf")
                blob.make_public()
                files_ref.push({
                    "date": upload_date.isoformat(),
                    "label": upload_label.strip() or upload_date.isoformat(),
                    "name": f.name,
                    "url": blob.public_url
                })
            st.success(f"✅ {len(uploaded_pdfs)} file(s) uploaded")
            rerun()

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
                            st.markdown(f"📄 [{f['name']}]({f['url']})")
                        with col_b:
                            if st.button("🗑️", key=f"del_{f['key']}"):
                                bucket = storage.bucket()
                                bucket.blob(f"camp/{d}/{f['name']}").delete()
                                files_ref.child(f["key"]).delete()
                                rerun()


# MY MEMOS
if page == "📅 My Memos" and site == "cfc":
    st.title("📅 My Memos")

    selected_staff = st.selectbox("Who are you?", [""] + STAFF)
    if not selected_staff:
        st.info("Select your name to view your memos.")
        st.stop()

    memos_data = fetch_memos()
    today = datetime.datetime.now(MT).date()

    # Collect all memo dates for this staff member from today onward
    upcoming = []
    for k, v in memos_data.items():
        if v.get("staff") == selected_staff and v.get("memo", "").strip():
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
        selected_date_str = st.selectbox("Select a date:", dates)
        memo_for_date = next(m for d, m in upcoming if str(d) == selected_date_str)
        st.divider()
        st.markdown(memo_for_date, unsafe_allow_html=True)


# RESOURCES
if page == "📁 Resources" and site == "cfc":
    st.title("📁 Resources")

    all_files = fetch_files()
    if not all_files:
        st.info("No files uploaded yet.")
    else:
        today = datetime.datetime.now(MT).date()
        files_by_date = {}
        for k, v in all_files.items():
            try:
                d = datetime.date.fromisoformat(v.get("date", ""))
            except ValueError:
                continue
            files_by_date.setdefault(d, []).append(v)

        past = {d: f for d, f in files_by_date.items() if d < today}
        upcoming = {d: f for d, f in files_by_date.items() if d >= today}

        if upcoming:
            st.subheader("📅 Upcoming")
            for d in sorted(upcoming.keys()):
                label = upcoming[d][0].get("label", str(d))
                with st.expander(f"{d} — {label}"):
                    for f in upcoming[d]:
                        st.markdown(f"📄 [{f['name']}]({f['url']})")

        if past:
            st.subheader("🗂️ Past")
            for d in sorted(past.keys(), reverse=True):
                label = past[d][0].get("label", str(d))
                with st.expander(f"{d} — {label}"):
                    for f in past[d]:
                        st.markdown(f"📄 [{f['name']}]({f['url']})")

