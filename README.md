# 🏥 Patient Outcomes Dashboard

A Streamlit web application for exploring breast cancer patient outcomes using the **CMS Synthetic Patient Data (SynPUF)** dataset via Google BigQuery (OMOP CDM format).

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-red?style=flat-square)
![BigQuery](https://img.shields.io/badge/Google_BigQuery-OMOP-4285F4?style=flat-square)
![Altair](https://img.shields.io/badge/Altair-5.3%2B-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## Overview

This dashboard connects to Google BigQuery's publicly available CMS SynPUF OMOP dataset to build a breast cancer patient cohort on the fly, then presents interactive visualizations of treatment timing, mortality, and age at diagnosis.

**Key features:**

- Automated ETL via BigQuery views (cohort creation + treatment group classification) on load
- Interactive donut + bar chart with cross-filtering by treatment group
- Age at diagnosis histogram filterable by race/ethnicity
- Summary KPI cards (total patients, 1-year mortality, mortality rate, treatment groups)
- Raw data preview with column selection
- Dark-themed, responsive UI built with Streamlit and Altair

---

## Dashboard Preview

| Section | Description |
|---|---|
| **KPI Cards** | Total patients, died within 1 year, mortality rate, number of treatment groups |
| **Treatment Group Overview** | Donut chart (share by group) linked to bar chart (1-year deaths by group) |
| **Age at Diagnosis** | Histogram with race/ethnicity dropdown filter |
| **Raw Data Preview** | Scrollable table of up to 200 records |

---

## Data & Cohort Definition

**Source:** [`bigquery-public-data.cms_synthetic_patient_data_omop`](https://console.cloud.google.com/marketplace/product/hhs/synpuf)

**Cohort inclusion criteria:**
- Female patients (`gender_concept_id = 8532`)
- At least one condition occurrence matching breast cancer concepts (`female breast`, `breast cancer`, `neoplasm breast`)

**Treatment groups** are assigned based on days from first diagnosis to first recorded treatment (procedure or drug exposure):

| Group | Definition |
|---|---|
| Early treatment | 0 – 30 days post-diagnosis |
| Late treatment | 31 – 90 days post-diagnosis |
| Very late treatment | > 90 days post-diagnosis |
| Treatment before recorded diagnosis | Negative days-to-treatment |
| No treatment | No procedure or drug exposure found |

---

## Project Structure

```
.
├── app.py                          # Main Streamlit application
├── requirements.txt                # Python dependencies
├── your-service-account-key.json   # GCP service account key (not committed)
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- A Google Cloud project with BigQuery API enabled
- Access to the `bigquery-public-data.cms_synthetic_patient_data_omop` dataset
- A BigQuery dataset named `breast_cancer_study` in your project (for writing views)
- A GCP service account JSON key with the following roles:
  - `BigQuery Data Viewer` (on the public dataset)
  - `BigQuery Data Editor` (on your `breast_cancer_study` dataset)
  - `BigQuery Job User`

> 🔑 **A GCP service account key is required to run this app.** The dashboard authenticates with BigQuery using a service account — even though the underlying data is fully synthetic and publicly available, BigQuery still requires a GCP identity to execute queries and bill job costs to a project. The key is **not included in this repository** and must be set up separately (see steps below).

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-username/patient-outcomes-dashboard.git
   cd patient-outcomes-dashboard
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your service account key**

   Create a GCP service account and download the JSON key from the [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts).

   **Option A — Local development:**

   Place the JSON key in the project root and update the filename in `app.py`:

   ```python
   with open("your-service-account-key.json") as f:
   ```

   Then add it to `.gitignore` so it's never committed:

   ```bash
   echo "*.json" >> .gitignore
   ```

   **Option B — Streamlit Community Cloud (recommended):**

   Go to your app's **Settings → Secrets** and paste the key contents in this format:

   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "your-project-id"
   private_key_id = "..."
   private_key = "-----BEGIN RSA PRIVATE KEY-----\n..."
   client_email = "your-sa@your-project.iam.gserviceaccount.com"
   client_id = "..."
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "..."
   ```

   Then update `get_bq_client()` in `app.py` to read from Streamlit secrets instead:

   ```python
   @st.cache_resource
   def get_bq_client():
       credentials = service_account.Credentials.from_service_account_info(
           st.secrets["gcp_service_account"]
       )
       return bigquery.Client(
           credentials=credentials,
           project=st.secrets["gcp_service_account"]["project_id"]
       )
   ```

4. **Create the BigQuery dataset**

   In your GCP project, create a dataset called `breast_cancer_study` — the app will create the views inside it automatically on first load.

5. **Run the app**

   ```bash
   streamlit run app.py
   ```

---

## Configuration

All BigQuery configuration lives at the top of `app.py`:

| Setting | Location in code | Description |
|---|---|---|
| Service account key path | `get_bq_client()` | Path to your JSON credentials file |
| Target dataset | `etl_query` | `breast_cancer_study` — change if needed |
| Cache TTL | `@st.cache_data(ttl=600)` | Seconds before re-querying BigQuery (default: 10 min) |

---

## Dependencies

See [`requirements.txt`](requirements.txt) for pinned versions. Key packages:

| Package | Purpose |
|---|---|
| `google-cloud-bigquery` | BigQuery client & query execution |
| `google-cloud-bigquery-storage` | Fast data transfer via Storage Read API |
| `db-dtypes` | Native BigQuery type support in pandas |
| `pyarrow` | Efficient columnar data transfer |
| `streamlit` | Web app framework |
| `altair` | Declarative interactive charts |
| `pandas` | Data manipulation |

---

## Notes

- The dataset used (`cms_synthetic_patient_data_omop`) is **fully synthetic** — it contains no real patient information.
- BigQuery views are recreated on every cold start (i.e., after cache expiry). This is fast but does require `BigQuery Data Editor` permissions on your target dataset.
- The dashboard is optimized for wide-layout screens.

---

## License

MIT — see [LICENSE](LICENSE) for details.
