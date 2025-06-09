import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import datetime
from pytz import timezone

# --- CONFIG ---
MT = timezone("US/Mountain")

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
        'databaseURL': 'https://polksdc-default-rtdb.firebaseio.com'
    })

# --- FIREBASE REFERENCES ---
staff_ref = db.reference("staff")
assignments_ref = db.reference("assignments")
logs_ref = db.reference("logs")
incidents_ref = db.reference("incidents")
memos_ref = db.reference("memos")

# --- HELPER ---
def safe_get(ref):
    return ref.get() or {}

# --- DEFAULT STAFF ---
default_staff_list = []
if not staff_ref.get():
    for name in default_staff_list:
        staff_ref.push({"name": name, "location": "Class 1"})

# --- HARD CODED LOCATIONS ---
LOCATIONS = ["Big Playground", "School Playground", "Field", "Bathroom", "Class 1", "Class 2", "Class 3", "Pool", "Field Trip", "Bus"]

# --- LOAD STAFF DATA ---
staff_data_raw = safe_get(staff_ref)
staff_lookup = {v["name"]: v.get("location", "Class 1") for v in staff_data_raw.values()}
STAFF = sorted(list(staff_lookup.keys()))

# --- LOAD ASSIGNMENTS ---
assignments_raw = safe_get(assignments_ref)
rows = []
for k, v in assignments_raw.items():
    rows.append({
        "id": k,
        "staff": v.get("staff", ""),
        "child": v.get("child", "")
    })
data = pd.DataFrame(rows, columns=["id", "staff", "child"])

# --- SIDEBAR STAFF MANAGEMENT ---
st.sidebar.header("Manage Staff")
new_staff_name = st.sidebar.text_input("Add Staff Name:")
new_staff_location = st.sidebar.selectbox("Default Location:", LOCATIONS)
if st.sidebar.button("Add Staff Member"):
    if new_staff_name.strip():
        staff_ref.push({"name": new_staff_name.strip(), "location": new_staff_location})
        st.sidebar.success(f"Added {new_staff_name}")
        st.rerun()

# --- PAGE NAVIGATION ---
page = st.sidebar.radio("Navigate", ["Staff View", "Admin View", "Memo Management"])

# ======================= STAFF VIEW =======================
if page == "Staff View":
    st.title("SDC Dashboard 😎")
    staff = st.selectbox("Select Staff:", [""] + STAFF)
    if not staff:
        st.stop()

    # Load all necessary data
    staff_data = safe_get(staff_ref)
    assignments_data = safe_get(assignments_ref)
    logs_data = safe_get(logs_ref)
    incidents_data = safe_get(incidents_ref)

    # MEMOS IN SIDEBAR
    with st.sidebar:
        st.subheader("📋 Today's Memo")
        memos_data = safe_get(memos_ref)
        today_iso = today_date()
        todays_memo = ""
        for v in memos_data.values():
            if v.get("staff") == staff and v.get("date") == today_iso:
                todays_memo = v.get("memo", "")
                break
        st.markdown(todays_memo or "✅ No memo assigned today.")

    staff_assignments = data[data["staff"] == staff]
    rows_with_index = staff_assignments.to_dict(orient="records")

    st.info("""- **KEEP LOCATION UPDATED 🎯**\n- 🧑‍🤝‍🧑 Count heads\n- ☀️ Sunscreen\n- 💧 Hydrate\n- ✅ Use Action Buttons\n- 📢 Walkie + App = safest""")

    with st.expander("🛠 Whole Group Actions", expanded=True):
        action_options = {
            "Care Actions": {"Accurate Headcount": "Headcount Confirmed","Ate": "Meal Confirmed", "Hydration": "Hydration Confirmed", "Sunscreen": "Sunscreen Applied"},
            # "Activity Participation": {"STEM": "STEM Activity Completed", "SEL": "SEL Activity Completed", "PE": "Physical Education Activity Completed", "ARTS": "Arts & Crafts Completed"}
        }
        category = st.radio("Action Type", list(action_options.keys()), key="cat")
        action_dict = action_options[category]
        selected_action = st.selectbox("Select Action", list(action_dict.keys()), key="act")
        if st.button("Confirm Action"):
            timestamp = now_timestamp()
            for row in rows_with_index:
                logs_ref.push({"timestamp": timestamp, "action": selected_action, "staff": staff, "child": row["child"], "notes": action_dict[selected_action]})
            st.success("✅ Logged for all")
            st.rerun()

    staff_location = staff_lookup.get(staff, "Class 1")
    new_location = st.text_input("Update Location:", value=staff_location)

    if staff_location != new_location:
        for key, value in staff_data_raw.items():
            if value["name"] == staff:
                staff_ref.child(key).update({"location": new_location})
                logs_ref.push({"timestamp": now_timestamp(), "action": "Location Update", "staff": staff, "child": "[LOCATION UPDATE]", "notes": f"Updated location to {new_location}"})
                break
        st.rerun()
        
    # st.subheader("Children", divider="gray")

    st.divider()
    # Initialize bathroom flags if not exists
    if "bathroom_flags" not in st.session_state:
        st.session_state.bathroom_flags = set()

    st.write(f" ##### ➕ Add Child to {staff}")
    new_child = st.text_input("Child name (First + Last Initial):", key="new_child_global")
    if st.button("Add Child ✅"):
        if new_child.strip():
            assignments_ref.push({"staff": staff, "child": new_child.strip()})
            logs_ref.push({"timestamp": now_timestamp(), "action": "Add", "staff": staff, "child": new_child.strip(), "notes": "Added"})
            st.rerun()

    # Active staff's children
    for i, row in enumerate(rows_with_index):
        child_name = row["child"]
        child_id = row["id"]
        
        # Add bathroom flag indicator if present
        bathroom_indicator = "🚽" if child_id in st.session_state.bathroom_flags else ""
        with st.expander(f"**{child_name}** {bathroom_indicator}"):
            st.write(f"Assigned to: {staff} | Location: {new_location}")
 # Bathroom flag toggle
            if child_id in st.session_state.bathroom_flags:
                if st.button("🚽", key=f"bathroom_{child_id}"):
                    st.session_state.bathroom_flags.remove(child_id)
                    st.rerun()
            else:
                if st.button("🚽 ", key=f"bathroom_{child_id}"):
                    st.session_state.bathroom_flags.add(child_id)
                    st.rerun()
            
            # Add tabs for different actions
            tab1, tab2, tab3, tab4 = st.tabs(["🔄 Move", "📝 Notes", "⚠️ Incident", "✏️ Edit"])
            
            with tab1:
                valid_staff_list = STAFF
                current_index = valid_staff_list.index(staff) if staff in valid_staff_list else 0
                new_staff_for_child = st.selectbox("Reassign:", valid_staff_list, index=current_index, key=f"move_{child_id}")
                if st.button("Confirm Move", key=f"btn_move_{child_id}"):
                    assignments_ref.child(child_id).update({"staff": new_staff_for_child, "child": child_name})
                    logs_ref.push({
                        "timestamp": now_timestamp(),
                        "action": "Move",
                        "staff": new_staff_for_child,
                        "child": child_name,
                        "notes": f"Moved from {staff} to {new_staff_for_child}"
                    })
                    st.success("Child reassigned!")
                    st.rerun()

                
               

                if f"confirm_checkout_{child_id}" not in st.session_state:
                    st.session_state[f"confirm_checkout_{child_id}"] = False
                if not st.session_state[f"confirm_checkout_{child_id}"]:
                    if st.button("✅ Check Out", key=f"checkout_{child_id}"):
                        st.session_state[f"confirm_checkout_{child_id}"] = True
                else:
                    st.warning("Confirm checkout?")
                    col_confirm, col_cancel = st.columns(2)
                    with col_confirm:
                        if st.button("Confirm", key=f"confirm_button_{child_id}"):
                            assignments_ref.child(child_id).delete()
                            logs_ref.push({
                                "timestamp": now_timestamp(),
                                "action": "Checkout",
                                "staff": staff,
                                "child": child_name,
                                "notes": "Checked Out"
                            })
                            del st.session_state[f"confirm_checkout_{child_id}"]
                            st.success("Checked out.")
                            st.rerun()
                    with col_cancel:
                        if st.button("Cancel", key=f"cancel_button_{child_id}"):
                            st.session_state[f"confirm_checkout_{child_id}"] = False
            
            with tab2:
                # Quick note options
                quick_notes = ["Bathroom Break", "Snack Time", "Playing Well", "Needs Support", "Great Behavior"]
                selected_quick_note = st.selectbox("Quick Notes:", [""] + quick_notes, key=f"quick_note_{child_id}")
                
                # Custom note input
                custom_note = st.text_input("Custom Note:", key=f"note_{child_id}")
                
                # Save note button
                if st.button("Save Note", key=f"save_note_{child_id}"):
                    note_text = selected_quick_note or custom_note
                    if note_text:
                        logs_ref.push({
                            "timestamp": now_timestamp(),
                            "action": "Note",
                            "staff": staff,
                            "child": child_name,
                            "notes": note_text
                        })
                        st.success("Note saved!")
                        st.rerun()
                
                # View previous notes
                st.write("Previous Notes:")
                notes = []
                for k, v in logs_data.items():
                    if v.get("child") == child_name and v.get("action") in ["Note", "Incident"]:
                        notes.append({
                            "timestamp": v.get("timestamp", ""),
                            "type": v.get("action", ""),
                            "staff": v.get("staff", ""),
                            "note": v.get("notes", "")
                        })
                
                if notes:
                    notes.sort(key=lambda x: x["timestamp"], reverse=True)
                    for note in notes[:5]:  # Show last 5 notes
                        st.markdown(f"""
                        *{note['timestamp']}* - **{note['type']}** by {note['staff']}:
                        > {note['note']}
                        """)
                    if len(notes) > 5:
                        with st.expander("View All Notes"):
                            for note in notes[5:]:
                                st.markdown(f"""
                                *{note['timestamp']}* - **{note['type']}** by {note['staff']}:
                                > {note['note']}
                                """)
                else:
                    st.info("No notes yet")

            with tab3:
                incident_note = st.text_input("Incident:", key=f"inc_{child_id}")
                if st.button("Save Incident", key=f"btn_inc_{child_id}"):
                    incidents_ref.push({
                        "timestamp": now_timestamp(),
                        "staff": staff,
                        "child": child_name,
                        "note": incident_note
                    })
                    st.success("Incident logged!")
                    st.rerun()

            with tab4:
                new_name = st.text_input("New Name:", value=child_name, key=f"rename_{child_id}")
                if st.button("Rename Child", key=f"btn_rename_{child_id}"):
                    if new_name.strip() and new_name != child_name:
                        assignments_ref.child(child_id).update({"child": new_name.strip()})
                        logs_ref.push({
                            "timestamp": now_timestamp(),
                            "action": "Rename",
                            "staff": staff,
                            "child": child_name,
                            "notes": f"Renamed to {new_name.strip()}"
                        })
                        st.success("Child renamed!")
                        st.rerun()

    

    # Other staff assignments
    st.write(f"🧑‍🏫 Under {staff}: **{len(rows_with_index)}**")
    st.write(f"🏕️ Total in Center: **{len(data)}**")

    st.subheader("Other Staff ", divider="gray")
    for other_staff in sorted(STAFF):
        if other_staff != staff:  # Skip current staff
            other_assignments = data[data["staff"] == other_staff]
            other_rows = other_assignments.sort_values("child").to_dict(orient="records")
            if other_rows:
                st.write(f"🧑‍🏫 *{other_staff}*: **{len(other_rows)}** -- {staff_lookup.get(other_staff, 'Class 1')}")
                for j, row in enumerate(other_rows):
                    child_name = row["child"]
                    child_id = row["id"]
                    
                    # Add bathroom flag indicator if present
                    bathroom_indicator = "🚽" if child_id in st.session_state.bathroom_flags else ""
                    with st.expander(f"**{child_name}** {bathroom_indicator}"):
                        st.write(f"Assigned to: {other_staff} | Location: {staff_lookup.get(other_staff, 'Class 1')}")
            # Bathroom flag toggle
                        if child_id in st.session_state.bathroom_flags:
                            if st.button("🚽", key=f"bathroom_{child_id}"):
                                st.session_state.bathroom_flags.remove(child_id)
                                st.rerun()
                        else:
                            if st.button("🚽 ", key=f"bathroom_{child_id}"):
                                st.session_state.bathroom_flags.add(child_id)
                                st.rerun()
                        # Add tabs for different actions
                        tab1, tab2, tab3, tab4 = st.tabs(["🔄 Move", "📝 Notes", "⚠️ Incident", "✏️ Edit"])
                        
                        with tab1:
                            valid_staff_list = STAFF
                            current_index = valid_staff_list.index(other_staff) if other_staff in valid_staff_list else 0
                            new_staff_for_child = st.selectbox("Reassign:", valid_staff_list, index=current_index, key=f"move_other_{child_id}")
                            if st.button("Confirm Move", key=f"btn_move_other_{child_id}"):
                                assignments_ref.child(child_id).update({"staff": new_staff_for_child, "child": child_name})
                                logs_ref.push({
                                    "timestamp": now_timestamp(),
                                    "action": "Move",
                                    "staff": new_staff_for_child,
                                    "child": child_name,
                                    "notes": f"Moved from {other_staff} to {new_staff_for_child}"
                                })
                                st.success("Child reassigned!")
                                st.rerun()

                           
                            if f"confirm_checkout_other_{child_id}" not in st.session_state:
                                st.session_state[f"confirm_checkout_other_{child_id}"] = False
                            if not st.session_state[f"confirm_checkout_other_{child_id}"]:
                                if st.button("✅ Check Out", key=f"checkout_other_{child_id}"):
                                    st.session_state[f"confirm_checkout_other_{child_id}"] = True
                            else:
                                st.warning("Confirm checkout?")
                                col_confirm, col_cancel = st.columns(2)
                                with col_confirm:
                                    if st.button("Confirm", key=f"confirm_button_other_{child_id}"):
                                        assignments_ref.child(child_id).delete()
                                        logs_ref.push({
                                            "timestamp": now_timestamp(),
                                            "action": "Checkout",
                                            "staff": other_staff,
                                            "child": child_name,
                                            "notes": "Checked Out"
                                        })
                                        del st.session_state[f"confirm_checkout_other_{child_id}"]
                                        st.success("Checked out.")
                                        st.rerun()
                                with col_cancel:
                                    if st.button("Cancel", key=f"cancel_button_other_{child_id}"):
                                        st.session_state[f"confirm_checkout_other_{child_id}"] = False
                        with tab2:
                            # Quick note options
                            quick_notes = ["Bathroom Break", "Snack Time", "Playing Well", "Needs Support", "Great Behavior"]
                            selected_quick_note = st.selectbox("Quick Notes:", [""] + quick_notes, key=f"quick_note_other_{child_id}")
                            
                            # Custom note input
                            custom_note = st.text_input("Custom Note:", key=f"note_other_{child_id}")
                            
                            # Save note button
                            if st.button("Save Note", key=f"save_note_other_{child_id}"):
                                note_text = selected_quick_note or custom_note
                                if note_text:
                                    logs_ref.push({
                                        "timestamp": now_timestamp(),
                                        "action": "Note",
                                        "staff": other_staff,
                                        "child": child_name,
                                        "notes": note_text
                                    })
                                    st.success("Note saved!")
                                    st.rerun()
                        
                            # View previous notes
                            st.write("Previous Notes:")
                            notes = []
                            for k, v in logs_data.items():
                                if v.get("child") == child_name and v.get("action") in ["Note", "Incident"]:
                                    notes.append({
                                        "timestamp": v.get("timestamp", ""),
                                        "type": v.get("action", ""),
                                        "staff": v.get("staff", ""),
                                        "note": v.get("notes", "")
                                    })
                            
                            if notes:
                                notes.sort(key=lambda x: x["timestamp"], reverse=True)
                                for note in notes[:5]:  # Show last 5 notes
                                    st.markdown(f"""
                                    *{note['timestamp']}* - **{note['type']}** by {note['staff']}:
                                    > {note['note']}
                                    """)
                                if len(notes) > 5:
                                    with st.expander("View All Notes"):
                                        for note in notes[5:]:
                                            st.markdown(f"""
                                            *{note['timestamp']}* - **{note['type']}** by {note['staff']}:
                                            > {note['note']}
                                            """)
                            else:
                                st.info("No notes yet")

                        with tab3:
                            incident_note = st.text_input("Incident:", key=f"inc_other_{child_id}")
                            if st.button("Save Incident", key=f"btn_inc_other_{child_id}"):
                                incidents_ref.push({
                                    "timestamp": now_timestamp(),
                                    "staff": other_staff,
                                    "child": child_name,
                                    "note": incident_note
                                })
                                st.success("Incident logged!")
                                st.rerun()

                        with tab4:
                            new_name = st.text_input("New Name:", value=child_name, key=f"rename_other_{child_id}")
                            if st.button("Rename Child", key=f"btn_rename_other_{child_id}"):
                                if new_name.strip() and new_name != child_name:
                                    assignments_ref.child(child_id).update({"child": new_name.strip()})
                                    logs_ref.push({
                                        "timestamp": now_timestamp(),
                                        "action": "Rename",
                                        "staff": other_staff,
                                        "child": child_name,
                                        "notes": f"Renamed to {new_name.strip()}"
                                    })
                                    st.success("Child renamed!")
                                    st.rerun()
                    # st.divider()
    # SWAP ROLES
    st.divider()
    with st.expander("🔄 Shift Change - Bulk Move"):
        col1, col2 = st.columns(2)
        with col1:
            from_staff = st.selectbox("From Staff:", STAFF, key="from_swap")
        with col2:
            to_staff = st.selectbox("To Staff:", STAFF, key="to_swap")
        if st.button("Swap Roles"):
            count = 0
            staff_assignments = data[data["staff"] == from_staff]
            for _, row in staff_assignments.iterrows():
                assignments_ref.child(row["id"]).update({"staff": to_staff, "child": row["child"]})
                logs_ref.push({"timestamp": now_timestamp(), "action": "Role Swap", "staff": to_staff, "child": row["child"], "notes": f"Moved from {from_staff} to {to_staff}"})
                count += 1
            st.success(f"Moved {count} children.")
            st.rerun()

# ADMIN VIEW
if page == "Admin View":
    st.title("📊 Admin Panel")
    
    # Emergency Actions at the top
    st.header("🚨 Emergency Actions")
    st.warning("⚠️ These actions are irreversible!")
    
    if "confirm_remove_all" not in st.session_state:
        st.session_state.confirm_remove_all = 0
        
    if st.session_state.confirm_remove_all == 0:
        if st.button("Remove All Children", key="remove_all_top"):
            st.session_state.confirm_remove_all = 1
    elif st.session_state.confirm_remove_all == 1:
        st.error("Are you absolutely sure? This will remove ALL children from the system.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, I'm Sure"):
                st.session_state.confirm_remove_all = 2
        with col2:
            if st.button("Cancel"):
                st.session_state.confirm_remove_all = 0
    elif st.session_state.confirm_remove_all == 2:
        st.error("⚠️ FINAL WARNING: This action cannot be undone!")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Confirm Remove All"):
                # Remove all assignments
                assignments_data = safe_get(assignments_ref)
                if assignments_data:  # Check if there are any assignments
                    for key in assignments_data.keys():
                        assignments_ref.child(key).delete()
                    # Log the action
                    logs_ref.push({
                        "timestamp": now_timestamp(),
                        "action": "EMERGENCY",
                        "staff": "ADMIN",
                        "child": "ALL",
                        "notes": "Emergency removal of all children"
                    })
                    st.success("✅ All children have been removed from the system")
                else:
                    st.info("No children in the system to remove")
                st.session_state.confirm_remove_all = 0
                st.rerun()
        with col2:
            if st.button("Cancel Emergency Action"):
                st.session_state.confirm_remove_all = 0

    st.divider()
    
    # Load Firebase data
    staff_data = safe_get(staff_ref)
    assignments_data = safe_get(assignments_ref)
    logs_data = safe_get(logs_ref)
    incidents_data = safe_get(incidents_ref)

    # Build staff lookup again (for safety)
    staff_lookup = {v["name"]: v.get("location", "N/A") for v in staff_data.values()}
    STAFF = sorted(list(staff_lookup.keys()))

    # Active Assignments
    st.header("👥 Active Assignments")

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
        count_by_staff = assignments_df.groupby("staff").size().reset_index(name="Child Count")

        with st.expander("📊 Children Count Per Staff", expanded=True):
            st.dataframe(count_by_staff, use_container_width=True)

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

    # Logs View
    st.header("📄 Logs Summary")

    # Date Filter for Logs
    selected_date = st.date_input("Filter Logs by Date:", datetime.datetime.now(MT).date())
    selected_date_str = selected_date.strftime("%B %d, %Y")
    
    # Filter logs by date
    log_rows = []
    for k, v in logs_data.items():
        timestamp = v.get("timestamp", "")
        if selected_date_str in timestamp:
            log_rows.append([
                timestamp,
                v.get("action", ""),
                v.get("staff", ""),
                v.get("child", ""),
                v.get("notes", "")
            ])

    logs_df = pd.DataFrame(log_rows, columns=["timestamp", "action", "staff", "child", "notes"])


    # All Logs View
    st.subheader("📄 All Logs")
    if logs_df.empty:
        st.success(f"✅ No logs found for {selected_date_str}")
    else:
        logs_df["parsed_timestamp"] = pd.to_datetime(logs_df["timestamp"], format="%B %d, %Y %I:%M %p", errors="coerce")
        logs_df = logs_df.sort_values(by="parsed_timestamp", ascending=False)

        with st.expander("📄 Full Logs", expanded=True):
            st.dataframe(
                logs_df.drop(columns=["parsed_timestamp"]),
                use_container_width=True,
                height=500
            )

        log_counts = logs_df["staff"].value_counts().reset_index()
        log_counts.columns = ["staff", "log_count"]

        with st.expander("📈 Log Counts Per Staff"):
            st.dataframe(log_counts, use_container_width=True)

    st.divider()

    # Emergency Actions
    with st.expander("🚨 Emergency Actions", expanded=False):
        st.warning("⚠️ These actions are irreversible!")
        
        if "confirm_remove_all" not in st.session_state:
            st.session_state.confirm_remove_all = 0
            
        if st.session_state.confirm_remove_all == 0:
            if st.button("Remove All Children", key="remove_all_emergency"):
                st.session_state.confirm_remove_all = 1
        elif st.session_state.confirm_remove_all == 1:
            st.error("Are you absolutely sure? This will remove ALL children from the system.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Yes, I'm Sure"):
                    st.session_state.confirm_remove_all = 2
            with col2:
                if st.button("Cancel"):
                    st.session_state.confirm_remove_all = 0
        elif st.session_state.confirm_remove_all == 2:
            st.error("⚠️ FINAL WARNING: This action cannot be undone!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Confirm Remove All"):
                    # Remove all assignments
                    assignments_data = safe_get(assignments_ref)
                    if assignments_data:  # Check if there are any assignments
                        for key in assignments_data.keys():
                            assignments_ref.child(key).delete()
                        # Log the action
                        logs_ref.push({
                            "timestamp": now_timestamp(),
                            "action": "EMERGENCY",
                            "staff": "ADMIN",
                            "child": "ALL",
                            "notes": "Emergency removal of all children"
                        })
                        st.success("✅ All children have been removed from the system")
                    else:
                        st.info("No children in the system to remove")
                    st.session_state.confirm_remove_all = 0
                    st.rerun()
            with col2:
                if st.button("Cancel Emergency Action"):
                    st.session_state.confirm_remove_all = 0

    st.divider()

    # Incidents View
    st.header("🚨 Incident Reports")

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

    # Database Management
    st.header("🗄️ Database Management")
    
    db_section = st.selectbox("Select Database:", [
        "Staff Records",
        "Assignment Records",
        "Log Records",
        "Incident Records",
        "Memo Records"
    ])

    if db_section == "Staff Records":
        st.subheader("👥 Staff Records")
        staff_records = []
        for k, v in staff_data.items():
            staff_records.append({
                "id": k,
                "name": v.get("name", ""),
                "location": v.get("location", "")
            })
        staff_df = pd.DataFrame(staff_records)
        if not staff_df.empty:
            st.dataframe(staff_df, use_container_width=True)
            selected_staff_id = st.selectbox("Select Record to Remove:", staff_df["id"], format_func=lambda x: f"{staff_df[staff_df['id'] == x]['name'].iloc[0]} ({x})")
            if selected_staff_id:
                staff_name = staff_df[staff_df["id"] == selected_staff_id]["name"].iloc[0]
                if st.button(f"🗑️ Remove Staff: {staff_name}"):
                    staff_ref.child(selected_staff_id).delete()
                    st.success(f"✅ Removed staff record for {staff_name}")
                    st.rerun()
        else:
            st.info("No staff records found")

    elif db_section == "Assignment Records":
        st.subheader("📋 Assignment Records")
        assignment_records = []
        for k, v in assignments_data.items():
            assignment_records.append({
                "id": k,
                "staff": v.get("staff", ""),
                "child": v.get("child", "")
            })
        assignments_df = pd.DataFrame(assignment_records)
        if not assignments_df.empty:
            st.dataframe(assignments_df, use_container_width=True)
            selected_assignment_id = st.selectbox("Select Record to Remove:", assignments_df["id"], 
                format_func=lambda x: f"{assignments_df[assignments_df['id'] == x]['child'].iloc[0]} (assigned to {assignments_df[assignments_df['id'] == x]['staff'].iloc[0]})")
            if selected_assignment_id:
                child_name = assignments_df[assignments_df["id"] == selected_assignment_id]["child"].iloc[0]
                if st.button(f"🗑️ Remove Assignment: {child_name}"):
                    assignments_ref.child(selected_assignment_id).delete()
                    st.success(f"✅ Removed assignment record for {child_name}")
                    st.rerun()
        else:
            st.info("No assignment records found")

    elif db_section == "Log Records":
        st.subheader("📝 Log Records")
        log_records = []
        for k, v in logs_data.items():
            log_records.append({
                "id": k,
                "timestamp": v.get("timestamp", ""),
                "action": v.get("action", ""),
                "staff": v.get("staff", ""),
                "child": v.get("child", ""),
                "notes": v.get("notes", "")
            })
        logs_df = pd.DataFrame(log_records)
        if not logs_df.empty:
            st.dataframe(logs_df, use_container_width=True)
            selected_log_id = st.selectbox("Select Record to Remove:", logs_df["id"], 
                format_func=lambda x: f"{logs_df[logs_df['id'] == x]['timestamp'].iloc[0]} - {logs_df[logs_df['id'] == x]['action'].iloc[0]}")
            if selected_log_id:
                log_info = logs_df[logs_df["id"] == selected_log_id].iloc[0]
                if st.button(f"🗑️ Remove Log: {log_info['timestamp']} - {log_info['action']}"):
                    logs_ref.child(selected_log_id).delete()
                    st.success("✅ Removed log record")
                    st.rerun()
        else:
            st.info("No log records found")

    elif db_section == "Incident Records":
        st.subheader("⚠️ Incident Records")
        incident_records = []
        for k, v in incidents_data.items():
            incident_records.append({
                "id": k,
                "timestamp": v.get("timestamp", ""),
                "staff": v.get("staff", ""),
                "child": v.get("child", ""),
                "note": v.get("note", "")
            })
        incidents_df = pd.DataFrame(incident_records)
        if not incidents_df.empty:
            st.dataframe(incidents_df, use_container_width=True)
            selected_incident_id = st.selectbox("Select Record to Remove:", incidents_df["id"], 
                format_func=lambda x: f"{incidents_df[incidents_df['id'] == x]['timestamp'].iloc[0]} - {incidents_df[incidents_df['id'] == x]['child'].iloc[0]}")
            if selected_incident_id:
                incident_info = incidents_df[incidents_df["id"] == selected_incident_id].iloc[0]
                if st.button(f"🗑️ Remove Incident: {incident_info['timestamp']} - {incident_info['child']}"):
                    incidents_ref.child(selected_incident_id).delete()
                    st.success("✅ Removed incident record")
                    st.rerun()
        else:
            st.info("No incident records found")

    elif db_section == "Memo Records":
        st.subheader("📝 Memo Records")
        memo_records = []
        for k, v in memos_data.items():
            memo_records.append({
                "id": k,
                "staff": v.get("staff", ""),
                "date": v.get("date", ""),
                "memo": v.get("memo", "")
            })
        memos_df = pd.DataFrame(memo_records)
        if not memos_df.empty:
            st.dataframe(memos_df, use_container_width=True)
            selected_memo_id = st.selectbox("Select Record to Remove:", memos_df["id"], 
                format_func=lambda x: f"{memos_df[memos_df['id'] == x]['date'].iloc[0]} - {memos_df[memos_df['id'] == x]['staff'].iloc[0]}")
            if selected_memo_id:
                memo_info = memos_df[memos_df["id"] == selected_memo_id].iloc[0]
                if st.button(f"🗑️ Remove Memo: {memo_info['date']} - {memo_info['staff']}"):
                    memos_ref.child(selected_memo_id).delete()
                    st.success("✅ Removed memo record")
                    st.rerun()
        else:
            st.info("No memo records found")

    st.divider()

    # Incidents View
    st.header("🚨 Incident Reports")

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

# MEMO MANAGEMENT

if page == "Memo Management":

    st.title("📝 Memo Management")

    # Load memos again
    memos_data = safe_get(memos_ref)

    selected_staff = st.selectbox("Staff for Memo:", STAFF)
    selected_date = st.date_input("Date", datetime.datetime.now(MT).date())

    # Attempt to prepopulate if memo exists
    memo_id, current_memo = None, ""
    for k, v in memos_data.items():
        if v.get("staff") == selected_staff and v.get("date") == selected_date.isoformat():
            memo_id, current_memo = k, v.get("memo", "")
            break

    col1, col2 = st.columns(2)

    with col1:
        memo_text = st.text_area("Memo Content:", value=current_memo, height=400)
        if st.button("Save Memo"):
            clean_memo = memo_text.replace("\r\n", "\n")
            data = {"staff": selected_staff, "date": selected_date.isoformat(), "memo": clean_memo}
            (memos_ref.child(memo_id).update if memo_id else memos_ref.push)(data)
            st.success("✅ Memo saved!")
            st.rerun()

        if memo_id and st.button("Delete Memo"):
            memos_ref.child(memo_id).delete()
            st.success("✅ Memo deleted.")
            st.rerun()

    with col2:
        st.markdown("### Live Preview:")
        st.markdown(memo_text or "*No memo content yet...*")

    st.divider()
    st.subheader("📝 Bulk Memo Distribution")

    bulk_date = st.date_input("Date for Bulk Memo:", datetime.datetime.now(MT).date(), key="bulk_date")
    bulk_memo = st.text_area("Bulk Memo Content:", height=200, key="bulk_memo")

    if st.button("Apply Memo to All Staff"):
        safe_bulk = bulk_memo.replace("\r\n", "\n")
        for staff_member in STAFF:
            existing = None
            for k, v in memos_data.items():
                if v.get("staff") == staff_member and v.get("date") == bulk_date.isoformat():
                    existing = k
                    break
            data = {"staff": staff_member, "date": bulk_date.isoformat(), "memo": safe_bulk}
            (memos_ref.child(existing).update if existing else memos_ref.push)(data)
        st.success("✅ Bulk memo assigned")
        st.rerun()
