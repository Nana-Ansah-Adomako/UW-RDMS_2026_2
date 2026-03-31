## Importing key packages
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd
import streamlit as st
import altair as alt
import os
import warnings
warnings.filterwarnings("ignore")


# page config 
st.set_page_config(page_title = "Patients Outcome Dashboard", page_icon = "🏥", layout = "wide")

# custom css - for dashboard appearance beautification,font styling, etc
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}
.stApp {
    background: #0f1e2b;
    color: #e8f0f7;
}
section[data-testid="stSidebar"] {
    background: #0a1520 !important;
    border-right: 1px solid #1e3448;
}
section[data-testid="stSidebar"] * {
    color: #c9daea !important;
}
.metric-card {
    background: #162535;
    border: 1px solid #1e3a50;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    text-align: center;
}
.metric-card .value {
    font-family: 'DM Serif Display', serif;
    font-size: 2.4rem;
    color: #4fc3f7;
    line-height: 1;
}
.metric-card .label {
    font-size: 0.78rem;
    color: #7fa8c4;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.3rem;
}
h1 {
    font-family: 'DM Serif Display', serif !important;
    color: #e8f0f7 !important;
}
h2, h3 {
    font-family: 'DM Serif Display', serif !important;
    color: #b8d8f0 !important;
}
hr { border-color: #1e3448; }
.vega-embed { background: transparent !important; }
</style>
""", unsafe_allow_html=True)


## Header
st.markdown("# 🏥 Patients Outcome Dashboard")
st.markdown("Breast cancer cohort from synpuf datasets")
st.markdown("---")


## Sidebar for Credentials input
with st.sidebar:
    st.markdown("### 🔑 BigQuery Authentication")
    credentials_file = st.file_uploader(
        "Upload service account JSON", type=["json"]
    )
    st.markdown("---")

## BigQuery client connection
@st.cache_resource
def get_bq_client(file_contents: str):
    import json
    info = json.loads(file_contents)
    credentials = service_account.Credentials.from_service_account_info(info)
    return bigquery.Client(credentials=credentials, project=info["project_id"])


## SQL query for ETL

etl_query = """ 
-- View for Breast Cancer cohort
CREATE OR REPLACE VIEW `breast_cancer_study.cohort` AS
SELECT 
    p.person_id,
    p.year_of_birth,
    p.race_concept_id,
    race.concept_name AS race_name,
    p.ethnicity_concept_id,
    ethnicity.concept_name AS ethnicity_name,

    MIN(co.condition_start_date) AS first_diagnosis_date,
    EXTRACT(YEAR FROM MIN(co.condition_start_date)) AS diagnosis_year,
    EXTRACT(YEAR FROM MIN(co.condition_start_date)) - p.year_of_birth AS age_at_diagnosis,

    d.death_date,
    EXTRACT(YEAR FROM d.death_date) AS death_year,
    CASE WHEN d.death_date IS NOT NULL THEN 'Deceased' ELSE 'Alive' END AS vital_status,
    DATE_DIFF(d.death_date, MIN(co.condition_start_date), DAY) AS survival_days
FROM `bigquery-public-data.cms_synthetic_patient_data_omop.person` AS p
JOIN `bigquery-public-data.cms_synthetic_patient_data_omop.condition_occurrence` AS co 
    ON p.person_id = co.person_id
JOIN `bigquery-public-data.cms_synthetic_patient_data_omop.concept` AS diagnosis 
    ON co.condition_concept_id = diagnosis.concept_id
LEFT JOIN `bigquery-public-data.cms_synthetic_patient_data_omop.concept` AS race 
    ON p.race_concept_id = race.concept_id
LEFT JOIN `bigquery-public-data.cms_synthetic_patient_data_omop.concept` AS ethnicity 
    ON p.ethnicity_concept_id = ethnicity.concept_id
LEFT JOIN `bigquery-public-data.cms_synthetic_patient_data_omop.death` AS d 
    ON p.person_id = d.person_id
WHERE p.gender_concept_id = 8532 
    AND (diagnosis.concept_name LIKE '%female breast%' 
    OR diagnosis.concept_name LIKE '%breast%cancer%' 
    OR diagnosis.concept_name LIKE '%neoplasm%breast%')
GROUP BY 
    p.person_id, 
    p.year_of_birth, 
    p.race_concept_id, 
    race.concept_name,
    p.ethnicity_concept_id,
    ethnicity.concept_name,
    d.death_date;


-- View for Breast cancer cohort with Treatment status
CREATE OR REPLACE VIEW `breast_cancer_study.cohort_with_treatment_groups` AS
SELECT 
    c.*,
    t.first_treatment_date,
    DATE_DIFF(t.first_treatment_date, c.first_diagnosis_date, DAY) AS days_to_treatment,
    CASE 
        WHEN t.first_treatment_date IS NULL THEN 'No treatment'
        WHEN DATE_DIFF(t.first_treatment_date, c.first_diagnosis_date, DAY) < 0 THEN 'Treatment before recorded diagnosis'
        WHEN DATE_DIFF(t.first_treatment_date, c.first_diagnosis_date, DAY) <= 30 THEN 'Early treatment (0-30 days)'
        WHEN DATE_DIFF(t.first_treatment_date, c.first_diagnosis_date, DAY) <= 90 THEN 'Late treatment (31-90 days)'
        ELSE 'Very late treatment (>90 days)'
    END AS treatment_group
FROM `breast_cancer_study.cohort` AS c
LEFT JOIN (
    SELECT 
        person_id,
        MIN(treatment_date) AS first_treatment_date
    FROM (
        SELECT person_id, procedure_datetime AS treatment_date
        FROM `bigquery-public-data.cms_synthetic_patient_data_omop.procedure_occurrence`
        UNION ALL
        SELECT person_id, drug_exposure_start_date AS treatment_date
        FROM `bigquery-public-data.cms_synthetic_patient_data_omop.drug_exposure`
    )
    GROUP BY person_id
) AS t ON c.person_id = t.person_id;
"""

fetch_query = """
-- cohort data  with treatment groups
SELECT * FROM `breast_cancer_study.cohort_with_treatment_groups`
"""

@st.cache_data(ttl=600, show_spinner="Querying BigQuery…")
def load_cohort(_client) -> pd.DataFrame:
    # Run etl query statements (views) — these return no rows
    _client.query(etl_query).result() #.result() blocks execution until the query completes.
    # Fetch data
    df = _client.query(fetch_query).to_dataframe()
    return df
## load data
if credentials_file:
    client = get_bq_client(credentials_file.getvalue().decode("utf-8"))
    df = load_cohort(client)
else:
    st.sidebar.warning("⬆️ Please upload your service account JSON to continue.")
    st.stop()


## summary statistics for dashboard PI metrics
# 1
total_patients = len(df)

# "Deceased" AND died within 365 days of diagnosis = Yes
df["died_within_1_year"] = "No"
mask_died_1yr = (
    (df["vital_status"] == "Deceased") &
    (df["survival_days"].notna()) &
    (df["survival_days"] <= 365)
    )

df.loc[mask_died_1yr, "died_within_1_year"] = "Yes"
# 2
died_within_1yr = (df["died_within_1_year"] == "Yes").sum()
# 3
pct_died = round(died_within_1yr / total_patients * 100, 2)
# 4
n_treatment_grps = df["treatment_group"].nunique()


## Displaying summary stats on dashboard
col1, col2, col3, col4 = st.columns(4)
for col, val, lbl in zip(
    [col1, col2, col3, col4],
    [f"{total_patients:,}", f"{died_within_1yr:,}", pct_died, str(n_treatment_grps)],
    ["Total Patients", "Died Within 1 Year", "Mortality Rate", "Treatment Groups"],
):
    with col:
        st.markdown(
            f'<div class="metric-card"><div class="value">{val}</div>'
            f'<div class="label">{lbl}</div></div>',
            unsafe_allow_html=True,
        )

st.markdown("---")


st.markdown("## Treatment Group Overview")
col_left, col_right = st.columns([1, 1.4])


## Visualization
CHART_BG   = "#162535"
GRID_COLOR = "#1e3a50"
TEXT_COLOR = "#b8d8f0"
BAR_COLOR  = "#4fc3f7"
BAR_COLOR2 = "#26c6da"

def chart_config(chart):
    return chart.configure_view(
        strokeOpacity=0,
        fill=CHART_BG,
    ).configure_axis(
        gridColor=GRID_COLOR,
        domainColor=GRID_COLOR,
        tickColor=GRID_COLOR,
        labelColor=TEXT_COLOR,
        titleColor=TEXT_COLOR,
        labelFont="DM Sans",
        titleFont="DM Sans",
    ).configure_title(
        color=TEXT_COLOR,
        font="DM Serif Display",
        fontSize=16,
    ).configure_legend(
        labelColor=TEXT_COLOR,
        titleColor=TEXT_COLOR,
        labelFont="DM Sans",
        titleFont="DM Sans",
    )

# donut plot
with col_left:
    treatment_counts = (
        df["treatment_group"]
        .value_counts()
        .reset_index()
    )
    treatment_counts.columns = ["treatment_group", "count"]
    treatment_counts["pct"] = (
        treatment_counts["count"] / treatment_counts["count"].sum() * 100
    ).round(1)
    treatment_counts["label"] = treatment_counts["pct"].astype(str) + "%"

    select = alt.selection_point(fields=["treatment_group"], on="click")

    donut = alt.Chart(treatment_counts).mark_arc(innerRadius=80, outerRadius=150).encode(
        theta=alt.Theta("count:Q", stack=True),
        order=alt.Order("count:Q", sort="descending"),
        color=alt.Color(
            "treatment_group:N",
            title="Treatment Group",
            scale=alt.Scale(scheme="blues"),
        ),
        opacity=alt.condition(select, alt.value(1), alt.value(0.3)),
        tooltip=[
            alt.Tooltip("treatment_group:N", title="Group"),
            alt.Tooltip("count:Q",           title="Patients"),
            alt.Tooltip("label:N",           title="Share"),
        ],
    ).add_params(select).properties(title=" ", width=700, height=300)

# bar plot
with col_right:
    df_died = df[df["died_within_1_year"] == "Yes"].copy()

    bar = alt.Chart(df_died).mark_bar(
        cornerRadiusTopLeft=4,
        cornerRadiusTopRight=4,
    ).encode(
        alt.X("treatment_group:N", title="Treatment Group",
              axis=alt.Axis(labelAngle=-30)).sort("-y"),
        alt.Y("count():Q", title="Number of Patients"),
        color=alt.Color("treatment_group:N", scale=alt.Scale(scheme="blues"), legend=None),
        opacity=alt.condition(select, alt.value(1), alt.value(0.3)),
        tooltip=[
            alt.Tooltip("treatment_group:N", title="Group"),
            alt.Tooltip("count():Q",          title="Deaths"),
        ],
    ).transform_filter(select).properties(title=" ", width=750, height=300)

combined = chart_config(donut | bar)
st.altair_chart(combined, use_container_width=True)


# OR stats table
@st.cache_data
def compute_summary(_df):
    groups = sorted(_df["treatment_group"].dropna().unique())
    ref_grp = groups[0]

    # Build raw counts first 
    rows = []
    contingency = []  # for multiple testing correction

    for grp in groups:
        g     = _df[_df["treatment_group"] == grp]
        died  = (g["died_within_1_year"] == "Yes").sum()
        alive = (g["died_within_1_year"] == "No").sum()
        rows.append({
            "Treatment Group": grp,
            "N":               len(g),
            "Died ≤1 Yr (n)": int(died),
            "Died ≤1 Yr (%)": f"{round(died / len(g) * 100, 1)}%",
            "_died":           died,
            "_alive":          alive,
        })
        contingency.append([died, alive])

    # Raw p-values via Fisher's exact (each group vs reference) 
    ref_died  = rows[0]["_died"]
    ref_alive = rows[0]["_alive"]
    raw_p     = []

    for row in rows:
        if row["Treatment Group"] == ref_grp:
            raw_p.append(np.nan)
            continue
        table = np.array([[row["_died"], row["_alive"]], [ref_died, ref_alive]])
        _, p  = stats.fisher_exact(table)
        raw_p.append(p)

    #  Benjamini-Hochberg FDR correction 
    non_ref_p   = [(i, p) for i, p in enumerate(raw_p) if not np.isnan(p)]
    m           = len(non_ref_p)
    sorted_p    = sorted(non_ref_p, key=lambda x: x[1])
    adjusted    = [np.nan] * len(raw_p)

    for rank, (i, p) in enumerate(sorted_p, start=1):
        adjusted[i] = min(p * m / rank, 1.0)

    # Odds Ratios + CI 
    summary = []
    for idx, row in enumerate(rows):
        grp   = row["Treatment Group"]
        died  = row["_died"]
        alive = row["_alive"]

        if grp == ref_grp:
            or_str, ci_str, p_str = "1.00 (ref)", "—", "—"
        elif 0 in [died, alive, ref_died, ref_alive]:
            or_str, ci_str, p_str = "N/A", "—", "—"
        else:
            OR     = (died * ref_alive) / (alive * ref_died)
            se     = np.sqrt(1/died + 1/alive + 1/ref_died + 1/ref_alive)
            lo, hi = np.exp(np.log(OR) - 1.96 * se), np.exp(np.log(OR) + 1.96 * se)
            adj_p  = adjusted[idx]
            or_str = f"{OR:.2f}"
            ci_str = f"{lo:.2f} – {hi:.2f}"
            p_str  = f"{adj_p:.3f}" if adj_p >= 0.001 else "<0.001"

        summary.append({
            "Treatment Group": grp,
            "Died ≤1 Yr (n)": row["Died ≤1 Yr (n)"],
            "Died ≤1 Yr (%)": row["Died ≤1 Yr (%)"],
            "OR (vs ref)":    or_str,
            "95% CI":         ci_str,
            "Adj. p-value":   p_str,
        })

    return pd.DataFrame(summary)

# Render 
st.markdown("#### 1-Year Mortality Odds by Treatment Group")

summary_df = compute_summary(df)

st.dataframe(
    summary_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "N": st.column_config.NumberColumn("N", format="%d"),
        "Died ≤1 Yr (n)": st.column_config.NumberColumn("Died ≤1yr (n)", format="%d"),
    }
)

ref_label = sorted(df["treatment_group"].dropna().unique())[0]
st.caption(
    f"OR = Odds Ratio for dying within 1 year vs **{ref_label}** (reference). "
    f"95% CI via Woolf method. P-value corrected for multiple comparisons using Benjamini-Hochberg FDR."
)



# filter by age
st.markdown("---")
st.markdown("## Age at Diagnosis Distribution")
st.caption("Filter by race using the dropdown below.")

race_options = sorted(df["race_name"].dropna().unique().tolist())
selected_race = st.selectbox("Select Race", options=["All"] + race_options)

df_hist = df.copy()
if selected_race != "All":
    df_hist = df_hist[df_hist["race_name"] == selected_race]

chart_age = chart_config(
    alt.Chart(df_hist).mark_bar(
        color=BAR_COLOR2,
        cornerRadiusTopLeft=3,
        cornerRadiusTopRight=3,
    ).encode(
        x=alt.X("age_at_diagnosis:Q",
                 bin=alt.Bin(maxbins=25),
                 title="Age at Diagnosis"),
        y=alt.Y("count():Q", title="Number of Patients"),
        tooltip=[
            alt.Tooltip("age_at_diagnosis:Q", title="Age", bin=True),
            alt.Tooltip("count():Q",           title="Count"),
        ],
    ).properties(
        title=f"Age at Diagnosis — {selected_race if selected_race != 'All' else 'All Races'}",
        width="container",
        height=380,
    )
)
st.altair_chart(chart_age, use_container_width=True)


## Raw data preview 
st.markdown("---")
with st.expander("🗂 Preview Raw Data"):
    preview_cols = [
        "person_id", "age_at_diagnosis", "race", "treatment_group",
        "died_within_1_year", "vital_status", "survival_days",
        "first_diagnosis_date", "death_date",
    ]
    # Only show columns that actually exist in the dataframe
    preview_cols = [c for c in preview_cols if c in df.columns]
    st.dataframe(
        df[preview_cols].head(200),
        use_container_width=True,
        height=300,
    )
    st.caption(f"Showing up to 200 of {len(df):,} data rows.")









