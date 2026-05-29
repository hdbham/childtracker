import streamlit as st
import duckdb
import pandas as pd
import io

st.title("Health Report Generator (HTML Export)")

uploaded_file = st.file_uploader("📂 Upload your Rosters Export CSV", type=["csv"])

if uploaded_file is not None:
    # Read CSV directly into pandas
    df_csv = pd.read_csv(uploaded_file)
    con = duckdb.connect(database=':memory:')
    con.register("roster", df_csv)

    cols = set(df_csv.columns.tolist())

    def col_expr(candidates, alias):
        match = next((c for c in candidates if c in cols), None)
        if match:
            return f'"{match}" AS {alias}'
        return f"NULL AS {alias}"

    select_parts = [
        col_expr(["Participant"], "Participant"),
        col_expr(["Age", "age", "participant-age", "age-years"], "Age"),
        col_expr(["t-shirt-size", "shirt-size", "tshirt-size", "Shirt Size", "shirt_size"], "ShirtSize"),
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
        df = con.execute(query).df()
    except Exception as e:
        st.error(f"Query failed: {e}")
        st.write("**Columns found in your CSV:**")
        st.write(list(cols))
        st.stop()
    df.columns = [col.replace("-", " ").replace("/", " ").title() for col in df.columns]

    # Build very basic HTML
    html_table = df.to_html(index=False, justify="center", border=1, escape=False)
    full_html = f"""
    <html>
    <head>
       
    </head>
    <body>
        <h2>YMCA Health & Emergency Summary</h2>
        {html_table}
    </body>
    </html>
    """

    # Create downloadable HTML file
    html_bytes = full_html.encode('utf-8')
    st.success("✅ Report generated!")
    st.download_button(
        label="📥 Download HTML Report",
        data=html_bytes,
        file_name="health_report.html",
        mime="text/html"
    )

else:
    st.info("👆 Please upload a CSV file to generate your report.")
