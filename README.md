Here is the complete documentation formatted as a single, production-ready `README.md` file for your GitHub repository.

---

```markdown
# Orion Academy KPI & LMS Analytics Engine

An automated analytics pipeline and interactive dashboard designed to extract, transform, and visualize learning KPIs from Orion’s Moodle LMS platform.

The system replaces manual monthly reporting with an automated data pipeline, providing executive leadership with visibility into training compliance, workforce learning reach, and module-level attrition.

---

## 1. System Architecture

The pipeline uses an automated, memory-bound ETL process that eliminates local disk storage:


```

┌──────────────────┐       ┌────────────────────────┐       ┌────────────────────────┐
│   MoodleCloud    │ ────► │ Microsoft Power        │ ────► │   SharePoint Online    │
│  (Report Export) │       │ Automate Cloud Flow    │       │   (latest_moodle_      │
└──────────────────┘       └────────────────────────┘       │    report.xlsx)        │
└───────────┬────────────┘
│
Microsoft Graph API
(App-Only Auth via MSAL)
│
▼
┌──────────────────────────────────┐               ┌────────────────────────┐
│ End-User Web Browser             │ ◄───────────  │  Azure Container App   │
│ Streamlit Interactive Dashboard  │  (Port 8501)  │  (Python 3.11 Runtime) │
└──────────────────────────────────┘               └────────────────────────┘

```

### Data Flow Breakdown
1. **Extraction**: MoodleCloud exports raw enrollment and completion metrics on a scheduled schedule.
2. **Transfer**: A Microsoft Power Automate flow captures the export and overwrites `latest_moodle_report.xlsx` inside a designated SharePoint folder.
3. **App-Only Authentication**: The Streamlit container authenticates against Microsoft Entra ID using the OAuth 2.0 Client Credentials flow (`msal-python`).
4. **In-Memory Streaming**: The workbook bytes are pulled over HTTPS via the Microsoft Graph API directly into an in-memory buffer (`io.BytesIO`) without being written to the container file system.
5. **Analytics & Visualization**: Pandas normalizes and aggregates the records; Plotly and Streamlit render the UI on Azure Container Apps.

---

## 2. Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Data Source** | MoodleCloud LMS | Source system for course activity, completion, and enrollments |
| **Orchestration** | Microsoft Power Automate | Automated scheduling and transfer of exported files to SharePoint |
| **Storage / Data Lake**| SharePoint Online | Centralized enterprise storage for `latest_moodle_report.xlsx` |
| **Identity & Access** | Microsoft Entra ID (Azure AD) | Service Principal registration for Graph API authentication |
| **Container Engine** | Docker Desktop / Docker Engine | Local container building and multi-architecture packaging |
| **Registry** | Azure Container Registry (ACR) | Image hosting (`lmsdashbaord.azurecr.io`) |
| **Hosting & Compute** | Azure Container Apps (ACA) | Serverless container environment running Streamlit on port `8501` |
| **Application Core** | Python 3.11, Streamlit, Pandas, MSAL, Requests, Plotly, OpenPyXL | Ingestion, data modeling, calculation, and UI presentation |

---

## 3. Microsoft Entra ID & API Permissions

The application uses an App Registration (Service Principal) for unattended background access.

* **Application (Client) ID**: `89814e2d-a7ce-4730-b16f-a055522e5707`
* **Directory (Tenant) ID**: `fda58d33-7098-40bb-8d52-891d51bb65e0`
* **Authentication Flow**: OAuth 2.0 Client Credentials (`/.default` scope)
* **API Permissions Type**: **Application Permissions** (App-only access; no signed-in user)
* **Required Microsoft Graph Scopes**:
  * `Sites.Read.All`: Resolve SharePoint site ID and document library drives
  * `Files.Read.All`: Read and download file contents via Graph drive item endpoints
* **Admin Consent**: Requires tenant-wide administrator consent (Status: **Granted**)

---

## 4. SharePoint Target Structure

The containerized service resolves the file location via Microsoft Graph using the following hierarchy:

* **SharePoint Domain**: `oriondigitalsolutions.sharepoint.com`
* **Site Relative Path**: `/sites/OrionGalaxyHub`
* **Target Document Library**: `Orion Documents`
* **File Target Path**: `Training/Organization Development/Orion Academy Files/LMS_Data/latest_moodle_report.xlsx`

---

## 5. Container App Environment Configuration

The Azure Container App runtime must have the following environment variables configured:

| Key | Type | Description |
| :--- | :--- | :--- |
| `AZURE_TENANT_ID` | Manual Entry | Corporate Microsoft Entra Tenant ID (`fda58d33-7098-40bb-8d52-891d51bb65e0`) |
| `AZURE_CLIENT_ID` | Manual Entry | App Registration Client ID (`89814e2d-a7ce-4730-b16f-a055522e5707`) |
| `AZURE_CLIENT_SECRET` | Secret Reference (`client-secret`) | Protected Client Secret value stored in ACA Secrets |

---

## 6. Local Build & Deployment Runbook

Deployments are built locally with **Docker Desktop** and pushed directly via the **Azure CLI (`az`)** without external CI/CD pipelines.

### Project Structure
```text
lms-dashboard/
├── Dockerfile
├── requirements.txt
└── app.py

```

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

```

### Build and Release Commands

#### Step 1: Build the Image Locally

> **Note**: Always include `--platform linux/amd64` to ensure the image matches Azure Container Apps' Linux runtime environment.

```powershell
docker build --platform linux/amd64 -t lmsdashbaord.azurecr.io/academy-kpi:v2 .

```

#### Step 2: Authenticate to ACR

```powershell
az acr login --name lmsdashbaord

```

#### Step 3: Push the Image to the Registry

```powershell
docker push lmsdashbaord.azurecr.io/academy-kpi:v2

```

#### Step 4: Deploy the Revision to Azure Container Apps

```powershell
az containerapp update `
  --name <CONTAINER_APP_NAME> `
  --resource-group <RESOURCE_GROUP_NAME> `
  --image lmsdashbaord.azurecr.io/academy-kpi:v2

```

*(Alternatively, update the revision via **Azure Portal** $\rightarrow$ **Container App** $\rightarrow$ **Containers** $\rightarrow$ **Edit and deploy** $\rightarrow$ choose tag `v2` $\rightarrow$ **Save**).*

---

## 7. Analytical KPI Methodology

The engine calculates metrics across all enrollments and learners on each run:

* **Overall Completion Rate (%)**:

$$\text{Completion Rate} = \left(\frac{\text{Count of Enrollments with 100\% Progress}}{\text{Total Enrollments}}\right) \times 100$$


* **Non-Starter Rate (%)**:

$$\text{Non-Starter Rate} = \left(\frac{\text{Count of Enrollments with 0\% Progress}}{\text{Total Enrollments}}\right) \times 100$$


* **Workforce Reach (%)**:

$$\text{Workforce Reach} = \left(\frac{\text{Unique Learners with } \ge 1 \text{ Completed Course}}{\text{Total Unique Enrolled Learners}}\right) \times 100$$


* **Fully Cleared Personnel**:
Count of individual learners whose completed course count matches 100% of their assigned courses.
* **Course Health & Drop-Off Threshold**:
Flags courses with an average completion rate below $70\%$ among cohorts with $\ge 5$ total enrollments.
* **Zero-Engagement Audit**:
Filters and highlights inactive personnel who have $0\%$ progress across every course assigned to them.

---

## 8. System Reference Links & Placeholders

Update these links as resources change:

* **Live Dashboard URL (Azure Container App)**: `[INSERT_CONTAINER_APP_FQDN_URL_HERE]`
* **Power Automate Cloud Flow**: `[INSERT_POWER_AUTOMATE_FLOW_DETAILS_OR_EDIT_URL_HERE]`
* **SharePoint Storage Location**: `[INSERT_SHARING_LINK_TO_LMS_DATA_SHAREPOINT_FOLDER_HERE]`
* **Azure Portal Resource Group / ACR**: `[INSERT_AZURE_PORTAL_RESOURCE_GROUP_URL_HERE]`

```

```
