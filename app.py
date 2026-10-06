import io
import os
import msal
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ==============================================================================
# 1. PAGE CONFIGURATION
# ==============================================================================
st.set_page_config(page_title="L&D Monthly KPI Engine", layout="wide")

# ==============================================================================
# 2. AZURE & SHAREPOINT CREDENTIALS
# ==============================================================================
TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")

# SharePoint Target Details
SHAREPOINT_DOMAIN = "oriondigitalsolutions.sharepoint.com"
SITE_REL_PATH = "/sites/OrionGalaxyHub"
DOCUMENT_LIBRARY = "Orion Documents"
FILE_PATH = "Training/Organization Development/Orion Academy Files/LMS_Data/latest_moodle_report.xlsx"

# Production check: verify all required environment variables exist
if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
    st.error(
        "⚠️ Missing required Azure credentials. "
        "Please ensure AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET "
        "are configured in the container environment settings."
    )
    st.stop()

# ==============================================================================
# 3. SHAREPOINT DATA INGESTION ENGINE
# ==============================================================================
@st.cache_data(ttl=3600, show_spinner="Syncing latest report from SharePoint...")
def fetch_from_sharepoint() -> pd.DataFrame:
    """Authenticates against Microsoft Graph and streams latest_moodle_report.xlsx into memory."""
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=authority,
        client_credential=CLIENT_SECRET,
    )
    token_response = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    
    if "access_token" not in token_response:
        raise ConnectionError(f"MS Graph Auth failed: {token_response.get('error_description')}")
        
    headers = {"Authorization": f"Bearer {token_response['access_token']}"}
    
    # Step A: Resolve SharePoint Site ID
    site_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_DOMAIN}:{SITE_REL_PATH}"
    site_res = requests.get(site_url, headers=headers)
    site_res.raise_for_status()
    site_id = site_res.json()["id"]
    
    # Step B: Resolve Drive (Document Library) ID
    drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    drives_res = requests.get(drives_url, headers=headers)
    drives_res.raise_for_status()
    drive_id = None
    for drive in drives_res.json().get("value", []):
        if drive["name"].strip() == DOCUMENT_LIBRARY.strip():
            drive_id = drive["id"]
            break
            
    if not drive_id:
        raise FileNotFoundError(f"Document Library '{DOCUMENT_LIBRARY}' was not found on SharePoint.")
        
    # Step C: Stream File Content Bytes
    file_endpoint = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{FILE_PATH}:/content"
    file_res = requests.get(file_endpoint, headers=headers)
    file_res.raise_for_status()
    
    # Step D: Load into Pandas directly from memory
    return pd.read_excel(io.BytesIO(file_res.content))

# ==============================================================================
# 4. DASHBOARD HEADER & SOURCE CONTROL
# ==============================================================================
st.title("📊 Orion Academy Monthly KPI Engine")

with st.sidebar:
    st.header("⚙️ Data Source Settings")
    data_source = st.radio(
        "Select Data Ingestion Method",
        ["Automatic (SharePoint Cloud Sync)", "Manual Upload (Ad-hoc File)"]
    )
    if data_source == "Automatic (SharePoint Cloud Sync)":
        if st.button("🔄 Force Refresh Cache"):
            st.cache_data.clear()
            st.rerun()

df = None

if data_source == "Automatic (SharePoint Cloud Sync)":
    try:
        df = fetch_from_sharepoint()
        st.caption("🟢 Live Data Source: Automated SharePoint Sync (`latest_moodle_report.xlsx`)")
    except Exception as err:
        st.warning(f"Could not load automated SharePoint sync: {err}")
        st.info("Falling back to manual upload mode.")
        uploaded_file = st.file_uploader("Upload Monthly Excel File", type=["xlsx", "xls"])
        if uploaded_file is not None:
            df = pd.read_excel(uploaded_file)
else:
    uploaded_file = st.file_uploader("Upload Monthly Excel File", type=["xlsx", "xls"])
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)

# ==============================================================================
# 5. DATA PREPARATION & NORMALIZATION
# ==============================================================================
if df is not None:
    col_course = [c for c in df.columns if "Course" in c][0]
    col_user = [c for c in df.columns if "Full name" in c or "User" in c][0]
    col_prog = [c for c in df.columns if "progress" in c.lower()][0]
    
    df["progress"] = df[col_prog].astype(str).str.rstrip("%").astype(float)
    
    total_enrollments = len(df)
    unique_users = df[col_user].nunique()
    total_courses = df[col_course].nunique()
    
    completed_enrollments = (df["progress"] == 100).sum()
    zero_enrollments = (df["progress"] == 0).sum()
    in_flight_enrollments = ((df["progress"] > 0) & (df["progress"] < 100)).sum()
    
    completion_rate = (completed_enrollments / total_enrollments) * 100 if total_enrollments > 0 else 0
    non_starter_rate = (zero_enrollments / total_enrollments) * 100 if total_enrollments > 0 else 0
    in_flight_rate = (in_flight_enrollments / total_enrollments) * 100 if total_enrollments > 0 else 0
    
    user_summary = df.groupby(col_user).agg(
        total_courses=("progress", "count"),
        completed=("progress", lambda x: (x == 100).sum()),
        zero_progress=("progress", lambda x: (x == 0).sum())
    )
    reach_users = (user_summary["completed"] > 0).sum()
    reach_rate = (reach_users / unique_users) * 100 if unique_users > 0 else 0
    fully_cleared_users = (user_summary["completed"] == user_summary["total_courses"]).sum()

    # ==============================================================================
    # 6. EXECUTIVE SCORECARD
    # ==============================================================================
    st.subheader("1. Executive Macro Scorecard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall Completion Rate", f"{completion_rate:.1f}%", f"{completed_enrollments}/{total_enrollments} completions")
    c2.metric("Non-Starter Rate (0%)", f"{non_starter_rate:.1f}%", f"{zero_enrollments} unstarted", delta_color="inverse")
    c3.metric("Workforce Reach", f"{reach_rate:.1f}%", f"{reach_users}/{unique_users} active learners")
    c4.metric("Fully Cleared Personnel", f"{fully_cleared_users}/{unique_users}", f"{(fully_cleared_users/unique_users)*100:.1f}% compliant")

    st.divider()

    # ==============================================================================
    # 7. INTERACTIVE VISUALIZATIONS
    # ==============================================================================
    st.subheader("2. Enrollment Distribution & Pipeline")
    col_chart1, col_chart2 = st.columns([1, 2])
    
    with col_chart1:
        status_counts = pd.DataFrame({
            "Status": ["Completed (100%)", "Non-Starter (0%)", "In-Flight (1-99%)"],
            "Count": [completed_enrollments, zero_enrollments, in_flight_enrollments]
        })
        fig_donut = px.pie(
            status_counts, 
            values="Count", 
            names="Status", 
            hole=0.5,
            color="Status",
            color_discrete_map={
                "Completed (100%)": "#10B981", 
                "Non-Starter (0%)": "#EF4444", 
                "In-Flight (1-99%)": "#F59E0B"
            }
        )
        fig_donut.update_layout(title="Enrollment Health Breakdown")
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_chart2:
        course_stats = df.groupby(col_course).agg(
            enrolled=("progress", "count"),
            completed=("progress", lambda x: (x == 100).sum()),
            avg_progress=("progress", "mean")
        ).reset_index()
        course_stats["completion_pct"] = (course_stats["completed"] / course_stats["enrolled"]) * 100
        course_stats = course_stats[course_stats["enrolled"] >= 5].sort_values(by="completion_pct", ascending=True)

        fig_bar = px.bar(
            course_stats,
            x="completion_pct",
            y=col_course,
            orientation="h",
            labels={"completion_pct": "Completion Rate (%)", col_course: "Course"},
            title="Course Completion Rate (Courses with ≥5 Enrollments)",
            color="completion_pct",
            color_continuous_scale="Blues"
        )
        fig_bar.add_vline(x=70, line_dash="dash", line_color="green", annotation_text="Target (70%)")
        st.plotly_chart(fig_bar, use_container_width=True)

    # ==============================================================================
    # 8. DIAGNOSTICS & DEEP DIVES
    # ==============================================================================
    st.subheader("3. Focus Areas: Onboarding & High Drop-Off Modules")
    col_ob, col_drop = st.columns(2)
    
    with col_ob:
        st.markdown("**Onboarding & Core Tracks**")
        onboarding_keywords = "Onboarding|Welcome|InfoSec|Orientation"
        ob_df = df[df[col_course].str.contains(onboarding_keywords, case=False, na=False)]
        
        if not ob_df.empty:
            ob_summary = ob_df.groupby(col_course).agg(
                Enrolled=("progress", "count"),
                Completed=("progress", lambda x: (x == 100).sum()),
                Zero_Prog=("progress", lambda x: (x == 0).sum()),
                Avg_Progress=("progress", "mean")
            ).reset_index()
            ob_summary["Completion Rate %"] = (ob_summary["Completed"] / ob_summary["Enrolled"]) * 100
            st.dataframe(ob_summary.style.format({"Avg_Progress": "{:.1f}%", "Completion Rate %": "{:.1f}%"}), use_container_width=True)
        else:
            st.info("No courses currently match the onboarding keyword filters.")

    with col_drop:
        st.markdown("**At-Risk Users (100% Inactive Across All Courses)**")
        inactive_list = user_summary[user_summary["zero_progress"] == user_summary["total_courses"]].reset_index()
        st.dataframe(
            inactive_list[[col_user, "total_courses"]].rename(columns={"total_courses": "Assigned Courses with 0% Progress"}),
            use_container_width=True
        )

else:
    st.info("👆 Please select an ingestion mode from the sidebar or upload a file.")