import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from datetime import datetime

st.set_page_config(
    page_title="Healthcare Operations Dashboard",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background-color: #0f1117; }

    /* Remove default top padding */
    .block-container { padding-top: 1.2rem !important; }

    /* KPI cards */
    [data-testid="metric-container"] {
        background: #1a1d27;
        border: 1px solid #2d3048;
        border-radius: 10px;
        padding: 16px 20px;
    }
    [data-testid="metric-container"] label {
        color: #8b92b3 !important;
        font-size: 0.73rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.04em;
    }
    [data-testid="stMetricValue"] {
        color: #e8eaf6 !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.8rem !important;
    }

    /* Brand header */
    .brand-title {
        font-size: 1.55rem;
        font-weight: 700;
        color: #e8eaf6;
        line-height: 1.2;
        margin-bottom: 0;
    }
    .brand-sub {
        color: #6b7280;
        font-size: 0.78rem;
        margin-top: 3px;
        margin-bottom: 0;
    }

    /* Sidebar: tighter, purposeful spacing (no dead whitespace) */
    [data-testid="stSidebar"] .block-container { padding-top: 1.4rem !important; }
    [data-testid="stSidebar"] hr { margin: 0.6rem 0 !important; border-color: #2d3048 !important; }
    .sb-label {
        color: #8b92b3;
        font-size: 0.66rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin: 0 0 3px 0;
    }
    .sb-value { color: #c5c8e0; font-size: 0.83rem; margin: 0 0 2px 0; }
    .sb-sub   { color: #6b7280; font-size: 0.7rem; margin: 0; }

    /* Top bar (every page) */
    .top-bar {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 0.5rem;
        padding-bottom: 0.6rem;
        border-bottom: 1px solid #2d3048;
    }
    .top-bar-title { font-size: 1.05rem; font-weight: 700; color: #e8eaf6; }
    .top-bar-time  { font-size: 0.72rem; color: #6b7280; }

    /* Page title */
    .page-title {
        font-size: 1.7rem;
        font-weight: 700;
        color: #e8eaf6;
        margin-bottom: 2px;
    }
    .page-sub {
        color: #6b7280;
        font-size: 0.84rem;
        margin-bottom: 1.1rem;
        line-height: 1.5;
    }
    .target-note {
        color: #6b7280;
        font-size: 0.72rem;
        margin: -6px 0 14px 0;
    }

    /* Section headers - varied sizes for hierarchy */
    .sec-lg {
        color: #c5c8e0;
        font-size: 1.0rem;
        font-weight: 600;
        margin: 1.8rem 0 0.3rem 0;
    }
    .sec-sm {
        color: #8b92b3;
        font-size: 0.82rem;
        font-weight: 600;
        margin: 1.2rem 0 0.2rem 0;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    /* Context text */
    .ctx {
        color: #6b7280;
        font-size: 0.79rem;
        margin-bottom: 0.6rem;
        line-height: 1.5;
    }

    /* Insight panel */
    .insight-panel {
        background: #1a1d27;
        border: 1px solid #2d3048;
        border-radius: 10px;
        padding: 16px;
        min-height: 100%;
        box-sizing: border-box;
    }
    .insight-panel h4 {
        color: #e8eaf6;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 0 0 12px 0;
        padding-bottom: 8px;
        border-bottom: 1px solid #2d3048;
    }
    .insight-item {
        color: #c5c8e0;
        font-size: 0.83rem;
        font-weight: 500;
        padding: 7px 0;
        border-bottom: 1px solid #1e2133;
        line-height: 1.45;
    }
    .insight-item:last-child { border-bottom: none; }
    .action-box {
        margin-top: 12px;
        padding: 10px 12px;
        background: #14251c;
        border: 1px solid #1f4a30;
        border-radius: 8px;
    }
    .action-label {
        color: #22c55e;
        font-size: 0.66rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .action-text { color: #c5c8e0; font-size: 0.79rem; line-height: 1.4; }

    /* Hide Streamlit's dev chrome — Deploy button, header bar, running/status widget */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    header[data-testid="stHeader"] {display: none;}
    [data-testid="stToolbar"] {display: none;}
    [data-testid="stDecoration"] {display: none;}
    [data-testid="stStatusWidget"] {display: none;}

    /* Cap multiselect height so a long clinic/department list scrolls
       instead of exploding the layout and clipping under the fold */
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
        max-height: 108px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

# ── Constants ────────────────────────────────────────────────────────────────
SLA_TARGET_MIN = 30
SLA_TARGET_PCT = 80

def fmt_pct(x):
    return f"{x:.1f}%"

def fmt_min(x):
    return f"{x:.0f} min"

def target_caption(extra=""):
    st.markdown(
        f'<p class="target-note">Target: ≤{SLA_TARGET_MIN} min waiting time · '
        f'{SLA_TARGET_PCT}% SLA compliance{(" · " + extra) if extra else ""}</p>',
        unsafe_allow_html=True,
    )

def render_top_bar():
    st.markdown(
        f'<div class="top-bar">'
        f'<span class="top-bar-title">Healthcare Operations Dashboard</span>'
        f'<span class="top-bar-time">Last updated: {datetime.now():%d %b %Y, %H:%M}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Color system ──────────────────────────────────────────────────────────────
C = dict(
    green  = "#22c55e",
    red    = "#ef4444",
    orange = "#f97316",
    blue   = "#3b82f6",
    purple = "#8b5cf6",
    grid   = "#1e2133",
    bg     = "#1a1d27",
    text   = "#c5c8e0",
)

def chart_base(**kw):
    d = dict(
        paper_bgcolor=C["bg"],
        plot_bgcolor=C["bg"],
        font=dict(color=C["text"], size=11),
        margin=dict(l=10, r=10, t=35, b=10),
        xaxis=dict(showgrid=True, gridcolor=C["grid"], zeroline=False,
                   linecolor="#2d3048", tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor=C["grid"], zeroline=False,
                   linecolor="#2d3048", tickfont=dict(size=10)),
    )
    d.update(kw)
    return d

# ── DB ────────────────────────────────────────────────────────────────────────
@st.cache_resource
def engine():
    h  = os.environ.get("CLINIC_DB_HOST", "localhost")
    p  = os.environ.get("CLINIC_DB_PORT", "5432")
    db = os.environ.get("CLINIC_DB_NAME", "clinic_db")
    u  = os.environ.get("CLINIC_DB_USER", "clinic_user")
    pw = os.environ.get("CLINIC_DB_PASS", "clinic_pass")
    return create_engine(f"postgresql+psycopg2://{u}:{pw}@{h}:{p}/{db}")

@st.cache_data(ttl=300)
def q(sql):
    with engine().connect() as c:
        return pd.read_sql(text(sql), c)

@st.cache_data(ttl=300)
def load_all():
    ns  = q("SELECT * FROM dbt_dev.mart_no_show_summary ORDER BY appointment_month")
    doc = q("SELECT * FROM dbt_dev.mart_doctor_utilization ORDER BY total_appointments DESC")
    sla = q("""
        SELECT s.*, c.latitude, c.longitude
        FROM dbt_dev.mart_sla_performance s
        LEFT JOIN dbt_dev.dim_clinics c ON s.clinic_id = c.clinic_id
    """)
    dow = q("""
        SELECT
            TRIM(TO_CHAR(scheduled_date, 'Day')) AS day_name,
            EXTRACT(DOW FROM scheduled_date) AS dow_num,
            d.department_name,
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'no_show' THEN 1 ELSE 0 END) AS noshows
        FROM dbt_dev.fact_appointments a
        LEFT JOIN dbt_dev.dim_departments d ON a.department_id = d.department_id
        WHERE status IN ('attended','no_show')
        GROUP BY 1,2,3
        ORDER BY 2
    """)
    try:
        pred = q("SELECT * FROM dbt_dev.mart_no_show_predictions ORDER BY no_show_probability DESC")
    except Exception:
        pred = pd.DataFrame()

    # Clinic-level granularity for filtering Overview / No-Show Analysis by clinic.
    # Best-effort: falls back gracefully if fact_appointments has no clinic_id.
    try:
        clinic_ns = q("""
            SELECT
                c.clinic_name,
                d.department_name,
                DATE_TRUNC('month', a.scheduled_date) AS appointment_month,
                COUNT(*) AS total,
                SUM(CASE WHEN a.status = 'no_show' THEN 1 ELSE 0 END) AS noshows,
                SUM(CASE WHEN a.status = 'attended' THEN 1 ELSE 0 END) AS attended
            FROM dbt_dev.fact_appointments a
            LEFT JOIN dbt_dev.dim_departments d ON a.department_id = d.department_id
            LEFT JOIN dbt_dev.dim_clinics c ON a.clinic_id = c.clinic_id
            WHERE a.status IN ('attended','no_show')
            GROUP BY 1,2,3
        """)
        has_clinic = True
    except Exception:
        clinic_ns = pd.DataFrame()
        has_clinic = False

    return ns, doc, sla, dow, pred, clinic_ns, has_clinic

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<p class="brand-title">Clinic Analytics</p>'
        '<p class="brand-sub">Healthcare Performance Monitoring<br>'
        'Sri Lanka Clinic Network &nbsp;·&nbsp; Synthetic Dataset 2025</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#4b5563;font-size:0.72rem;margin-top:6px">'
        'Streamlit · PostgreSQL · dbt · Random Forest</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    with st.spinner(""):
        ns_df, doc_df, sla_df, dow_df, pred_df, clinic_ns_df, HAS_CLINIC_DATA = load_all()

    ns_df["appointment_month"] = pd.to_datetime(ns_df["appointment_month"])
    DATA_START = ns_df["appointment_month"].min()
    DATA_END   = ns_df["appointment_month"].max()
    DATA_COVERAGE = f"{DATA_START:%b %Y} – {DATA_END:%b %Y}"

    st.markdown(
        f'<p class="sb-label">Data Coverage</p>'
        f'<p class="sb-value">{DATA_COVERAGE}</p>'
        f'<p class="sb-sub">{int(ns_df["total_appointments"].sum()):,} appointments · '
        f'{ns_df["department_name"].nunique()} departments</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    page = st.radio("", [
        "Overview",
        "No-Show Analysis",
        "Doctor Workload",
        "SLA & Wait Times",
        "No-Show Risk Prediction",
    ], label_visibility="collapsed")
    st.divider()
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Shared clinic-filter widget ───────────────────────────────────────────────
def clinic_picker(all_clinics, key_prefix, label="Clinic"):
    """Defaults to 'All clinics' (a single toggle) instead of pre-selecting every
    clinic as a pill — with 18+ clinics that used to overflow the filter row and
    get clipped. Unchecking reveals a scrollable multiselect to narrow down."""
    all_on = st.checkbox(f"All clinics ({len(all_clinics)})", value=True, key=f"{key_prefix}_all")
    if all_on:
        return all_clinics
    return st.multiselect(label, all_clinics, default=[], key=f"{key_prefix}_pick")

# ── Shared filtering helper (Department / Date / Clinic) ─────────────────────
def filter_ns(dept_sel, range_sel, clinic_sel=None, clinics_all=None):
    """Filter the no-show mart by department + month, optionally swapping to the
    clinic-level source when a clinic subset is selected."""
    use_clinic_src = (
        HAS_CLINIC_DATA and clinic_sel is not None and clinics_all is not None
        and set(clinic_sel) != set(clinics_all)
    )
    if use_clinic_src:
        src = clinic_ns_df.copy()
        src["appointment_month"] = pd.to_datetime(src["appointment_month"])
        src = src.rename(columns={
            "noshows": "no_show_count",
            "attended": "attended_count",
            "total": "total_appointments",
        })
        src = src[src["clinic_name"].isin(clinic_sel)]
    else:
        src = ns_df.copy()
    src = src[
        src["department_name"].isin(dept_sel) &
        (src["appointment_month"].dt.to_period("M").astype(str) >= range_sel[0]) &
        (src["appointment_month"].dt.to_period("M").astype(str) <= range_sel[1])
    ]
    return src

def month_delta(df, count_col):
    tmp = df.groupby("appointment_month")[count_col].sum().reset_index()
    tmp["appointment_month"] = pd.to_datetime(tmp["appointment_month"])
    tmp = tmp.sort_values("appointment_month")
    if len(tmp) >= 2:
        curr = tmp.iloc[-1][count_col]
        prev = tmp.iloc[-2][count_col]
        delta = round((curr - prev) / max(prev, 1) * 100, 1)
        return int(curr), delta
    return (int(tmp.iloc[-1][count_col]) if len(tmp) else 0), None

def compute_kpis(df):
    total   = int(df["total_appointments"].sum())
    noshows = int(df["no_show_count"].sum())
    att     = int(df["attended_count"].sum())
    rate    = round(100 * noshows / max(att + noshows, 1), 1)
    sla_avg = round(sla_df["sla_compliance_pct"].mean(), 1)
    wait    = round(doc_df["avg_wait_time_minutes"].mean())
    _, appt_delta = month_delta(df, "total_appointments")
    _, ns_delta   = month_delta(df, "no_show_count")
    return total, noshows, att, rate, sla_avg, wait, appt_delta, ns_delta

def dynamic_insights(df, wait):
    """Top 3 data-driven findings + one recommended action."""
    by_dept = (
        df.groupby("department_name")
        .agg(ns=("no_show_count", "sum"), att=("attended_count", "sum"))
    )
    by_dept = by_dept[(by_dept["ns"] + by_dept["att"]) > 0]
    if by_dept.empty:
        return [], None
    by_dept["rate"] = round(100 * by_dept["ns"] / (by_dept["att"] + by_dept["ns"]), 1)

    worst_dept, worst_rate = by_dept["rate"].idxmax(), by_dept["rate"].max()
    best_dept, best_rate   = by_dept["rate"].idxmin(), by_dept["rate"].min()
    sla_failing = int((sla_df["sla_compliance_pct"] < SLA_TARGET_PCT).sum())
    sla_total   = len(sla_df[sla_df["attended_appointments"] > 0])

    items = [
        (C["red"],    f"{worst_dept} has the highest no-show rate at {fmt_pct(worst_rate)}."),
        (C["green"],  f"{best_dept} performs best at {fmt_pct(best_rate)} no-shows."),
        (C["orange"], f"Waiting time averages {fmt_min(wait)}, "
                       f"{'above' if wait > SLA_TARGET_MIN else 'within'} the {SLA_TARGET_MIN}-min target."),
    ]
    action = (
        f"Focus reminder calls on {worst_dept} — its no-show rate is "
        f"{round(worst_rate - best_rate, 1)} points above {best_dept}, and "
        f"{sla_failing} of {sla_total} clinics are still below the {SLA_TARGET_PCT}% SLA target."
    )
    return items, action

render_top_bar()

# ════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ════════════════════════════════════════════════════════════════════════
if page == "Overview":
    st.markdown('<p class="page-title">Overview</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-sub">Track patient attendance, waiting times, and clinic '
        'performance across the Sri Lanka network.</p>',
        unsafe_allow_html=True,
    )

    # ── Filters ───────────────────────────────────────────────────────────────
    depts_all   = sorted(ns_df["department_name"].unique().tolist())
    months_all  = sorted(ns_df["appointment_month"].dt.to_period("M").astype(str).unique())
    clinics_all = sorted(clinic_ns_df["clinic_name"].dropna().unique().tolist()) if HAS_CLINIC_DATA else []

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        ov_dept = st.multiselect("Department", depts_all, default=depts_all, key="ov_dept")
    with fc2:
        ov_range = st.select_slider("Date range", options=months_all,
                                     value=(months_all[0], months_all[-1]), key="ov_range")
    with fc3:
        if HAS_CLINIC_DATA:
            ov_clinic = clinic_picker(clinics_all, "ov")
        else:
            ov_clinic = None
            st.caption("Clinic-level filtering isn't available for this view.")

    ov_df = filter_ns(ov_dept, ov_range, ov_clinic, clinics_all)

    total, noshows, att, rate, sla_avg, wait, appt_delta, ns_delta = compute_kpis(ov_df)

    # ── 3 KPIs (not 5 — hierarchy) ───────────────────────────────────────────
    k1, k2, k3 = st.columns(3)
    ad = f"{appt_delta:+.1f}% vs last month" if appt_delta is not None else None
    nd = f"{ns_delta:+.1f}% vs last month"   if ns_delta   is not None else None

    k1.metric("Total Appointments",   f"{total:,}",   delta=ad)
    k2.metric("Missed Appointments",  f"{noshows:,} patients", delta=nd, delta_color="inverse")
    k3.metric("Average Waiting Time", fmt_min(wait),
              delta=f"{'above' if wait > SLA_TARGET_MIN else 'within'} {SLA_TARGET_MIN}-min target",
              delta_color="inverse" if wait > SLA_TARGET_MIN else "normal")
    target_caption()

    # ── Main trend (70%) + Insights panel (30%) ──────────────────────────────
    st.markdown('<p class="sec-lg">Appointment No-Show Rate — Monthly Trend</p>',
                unsafe_allow_html=True)

    main_col, insight_col = st.columns([7, 3])

    with main_col:
        monthly = (
            ov_df.groupby("appointment_month")
            .agg(ns=("no_show_count", "sum"), att=("attended_count", "sum"))
            .reset_index()
        )
        monthly["rate"] = round(100 * monthly["ns"] / (monthly["att"] + monthly["ns"]), 1)
        monthly["appointment_month"] = pd.to_datetime(monthly["appointment_month"])
        monthly = monthly.sort_values("appointment_month")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=monthly["appointment_month"], y=monthly["rate"],
            mode="lines+markers",
            line=dict(color=C["red"], width=2.5),
            marker=dict(color=C["red"], size=5),
            fill="tozeroy",
            fillcolor="rgba(239,68,68,0.08)",
            name="No-Show %",
            hovertemplate="%{x|%b %Y}: %{y:.1f}%<extra></extra>",
        ))
        fig.add_hline(y=rate, line_dash="dot", line_color="#4b5563",
                      annotation_text=f"Overall avg: {fmt_pct(rate)}",
                      annotation_font_color="#6b7280", annotation_font_size=10)
        fig.update_layout(**chart_base(
            yaxis_title="No-Show Rate (%)", xaxis_title="",
            showlegend=False, height=300,
        ))
        st.plotly_chart(fig, use_container_width=True)

    with insight_col:
        items, action = dynamic_insights(ov_df, wait)
        items_html = "".join([
            f'<div class="insight-item"><span style="color:{col}">●</span> {txt}</div>'
            for col, txt in items
        ])
        action_html = (
            f'<div class="action-box"><div class="action-label">Recommended Action</div>'
            f'<div class="action-text">{action}</div></div>' if action else ""
        )
        stat_strip = (
            f'<div style="display:flex;gap:16px;margin-top:12px;padding-top:10px;'
            f'border-top:1px solid #2d3048;">'
            f'<div><div class="sb-label" style="margin:0">No-Show Rate</div>'
            f'<div style="color:#e8eaf6;font-size:1.1rem;font-weight:700;">{fmt_pct(rate)}</div></div>'
            f'<div><div class="sb-label" style="margin:0">SLA Compliance</div>'
            f'<div style="color:#e8eaf6;font-size:1.1rem;font-weight:700;">{fmt_pct(sla_avg)}</div></div>'
            f'</div>'
        )
        st.markdown(
            f'<div class="insight-panel"><h4>Key Findings</h4>{items_html}{action_html}{stat_strip}</div>',
            unsafe_allow_html=True,
        )

    # ── Bottom row: two charts with different heights ─────────────────────────
    st.markdown("<div style='margin-top:0.4rem'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns([5, 5])

    with col1:
        st.markdown('<p class="sec-lg">Departments with the Highest No-Show Rates</p>',
                    unsafe_allow_html=True)
        dept = (
            ov_df.groupby("department_name")
            .agg(ns=("no_show_count", "sum"), att=("attended_count", "sum"))
            .reset_index()
        )
        dept["rate"] = round(100 * dept["ns"] / (dept["att"] + dept["ns"]), 1)
        dept = dept.sort_values("rate")
        colors = [C["red"] if r > 25 else C["orange"] if r > 20 else C["green"]
                  for r in dept["rate"]]
        fig2 = go.Figure(go.Bar(
            x=dept["rate"], y=dept["department_name"], orientation="h",
            marker_color=colors,
            text=dept["rate"].apply(lambda x: fmt_pct(x)),
            textposition="outside",
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
        ))
        fig2.update_layout(**chart_base(
            xaxis_title="No-Show Rate (%)", yaxis_title="",
            showlegend=False, height=260,
        ))
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.markdown('<p class="sec-lg">Patient Appointment Outcomes</p>',
                    unsafe_allow_html=True)
        cancelled = int(ov_df["cancelled_count"].sum()) if "cancelled_count" in ov_df.columns else 0
        status_df = pd.DataFrame({
            "Outcome": ["Attended", "No-Show", "Cancelled"],
            "Count":   [att, noshows, cancelled],
        })
        fig3 = go.Figure(go.Pie(
            labels=status_df["Outcome"], values=status_df["Count"],
            hole=0.55,
            marker_colors=[C["green"], C["red"], C["orange"]],
            textinfo="percent+label", textposition="outside",
            hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>",
        ))
        fig3.update_layout(**chart_base(showlegend=False, height=260))
        st.plotly_chart(fig3, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════
# NO-SHOW ANALYSIS
# ════════════════════════════════════════════════════════════════════════
elif page == "No-Show Analysis":
    st.markdown('<p class="page-title">No-Show Analysis</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-sub">Explore where and when patients are most likely to miss appointments.</p>',
        unsafe_allow_html=True,
    )

    # ── Filters ───────────────────────────────────────────────────────────────
    depts = sorted(ns_df["department_name"].unique().tolist())
    ns_df["appointment_month"] = pd.to_datetime(ns_df["appointment_month"])
    months = sorted(ns_df["appointment_month"].dt.to_period("M").unique())
    months_str = [str(m) for m in months]
    clinics_all = sorted(clinic_ns_df["clinic_name"].dropna().unique().tolist()) if HAS_CLINIC_DATA else []

    f1, f2, f3 = st.columns(3)
    with f1:
        sel_dept = st.multiselect("Filter by department", depts, default=depts)
    with f2:
        sel_range = st.select_slider(
            "Date range",
            options=months_str,
            value=(months_str[0], months_str[-1]),
        )
    with f3:
        if HAS_CLINIC_DATA:
            sel_clinic = clinic_picker(clinics_all, "nsa")
        else:
            sel_clinic = None
            st.caption("Clinic-level filtering isn't available for this view.")

    filt = filter_ns(sel_dept, sel_range, sel_clinic, clinics_all)

    total, noshows, att, rate, sla_avg, wait, _, _ = compute_kpis(filt)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Appointments", f"{total:,}")
    k2.metric("Missed Appointments", f"{noshows:,}")
    k3.metric("No-Show Rate", fmt_pct(rate))
    k4.metric("Attendance Rate", fmt_pct(round(100 - rate, 1)))

    st.markdown('<p class="sec-lg">No-Show Rate Over Time</p>', unsafe_allow_html=True)
    trend = (
        filt.groupby(["appointment_month", "department_name"])
        .agg(ns=("no_show_count", "sum"), att=("attended_count", "sum"))
        .reset_index()
    )
    trend["no_show_rate_pct"] = round(100 * trend["ns"] / (trend["att"] + trend["ns"]), 1)
    fig = px.line(
        trend, x="appointment_month", y="no_show_rate_pct", color="department_name",
        markers=True,
        color_discrete_sequence=[C["red"], C["orange"], C["blue"], C["green"], C["purple"], "#e879f9"],
        labels={"appointment_month": "", "no_show_rate_pct": "No-Show Rate (%)", "department_name": "Department"},
    )
    fig.update_layout(**chart_base(height=320))
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="sec-lg">No-Shows by Day of Week</p>', unsafe_allow_html=True)
        st.markdown('<p class="ctx">Which days see the most missed appointments?</p>', unsafe_allow_html=True)
        dow_filt = dow_df[dow_df["department_name"].isin(sel_dept)].copy()
        day_summary = (
            dow_filt.groupby(["day_name", "dow_num"])
            .agg(total=("total", "sum"), ns=("noshows", "sum"))
            .reset_index()
            .sort_values("dow_num")
        )
        day_summary["rate"] = round(100 * day_summary["ns"] / day_summary["total"], 1)
        fig_dow = go.Figure(go.Bar(
            x=day_summary["day_name"].str.strip(),
            y=day_summary["rate"],
            marker_color=[C["red"] if r > day_summary["rate"].mean() else C["blue"]
                          for r in day_summary["rate"]],
            text=day_summary["rate"].apply(lambda x: fmt_pct(x)),
            textposition="outside",
        ))
        fig_dow.update_layout(**chart_base(
            yaxis_title="No-Show Rate (%)", xaxis_title="",
            showlegend=False, height=270,
        ))
        st.plotly_chart(fig_dow, use_container_width=True)

    with col2:
        st.markdown('<p class="sec-lg">No-Show Heatmap — Department vs Day</p>',
                    unsafe_allow_html=True)
        st.markdown('<p class="ctx">Darker red = higher no-show rate.</p>', unsafe_allow_html=True)
        dow_filt2 = dow_df[dow_df["department_name"].isin(sel_dept)].copy()
        dow_filt2["rate"] = round(100 * dow_filt2["noshows"] / dow_filt2["total"], 1)
        heat_pivot = dow_filt2.pivot_table(
            index="department_name", columns="day_name",
            values="rate", aggfunc="mean"
        )
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        heat_cols = [d.strip() for d in heat_pivot.columns]
        ordered = [d for d in day_order if d in heat_cols]
        heat_pivot.columns = heat_pivot.columns.str.strip()
        heat_pivot = heat_pivot[[c for c in ordered if c in heat_pivot.columns]]

        fig_heat = go.Figure(go.Heatmap(
            z=heat_pivot.values,
            x=heat_pivot.columns.tolist(),
            y=heat_pivot.index.tolist(),
            colorscale=[[0, "#1a2f5a"], [0.5, "#f97316"], [1, "#ef4444"]],
            text=heat_pivot.values.round(1),
            texttemplate="%{text}%",
            showscale=True,
            colorbar=dict(title="No-Show %", tickfont=dict(color=C["text"])),
        ))
        fig_heat.update_layout(**chart_base(height=270, margin=dict(l=10, r=10, t=10, b=10)))
        st.plotly_chart(fig_heat, use_container_width=True)

    st.markdown('<p class="sec-lg">Average Days Between Booking and Appointment</p>',
                unsafe_allow_html=True)
    st.markdown('<p class="ctx">Patients who book further ahead are more likely to forget — '
                'longer bars signal higher reminder priority. Based on department + date filters only.</p>',
                unsafe_allow_html=True)
    lead_src = ns_df[
        ns_df["department_name"].isin(sel_dept) &
        (ns_df["appointment_month"].dt.to_period("M").astype(str) >= sel_range[0]) &
        (ns_df["appointment_month"].dt.to_period("M").astype(str) <= sel_range[1])
    ]
    lead = (
        lead_src.groupby("department_name")["avg_lead_time_days"].mean().reset_index()
        .sort_values("avg_lead_time_days", ascending=False)
    )
    fig_lead = go.Figure(go.Bar(
        x=lead["department_name"],
        y=lead["avg_lead_time_days"],
        marker_color=C["blue"],
        text=lead["avg_lead_time_days"].round(1),
        texttemplate="%{text}d", textposition="outside",
    ))
    fig_lead.update_layout(**chart_base(
        yaxis_title="Avg Days in Advance", xaxis_title="",
        showlegend=False, height=260,
    ))
    st.plotly_chart(fig_lead, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════
# DOCTOR WORKLOAD
# ════════════════════════════════════════════════════════════════════════
elif page == "Doctor Workload":
    st.markdown('<p class="page-title">Doctor Workload Distribution</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-sub">Appointment volume and no-show rates per doctor. '
        'Identifies who carries the most risk.</p>',
        unsafe_allow_html=True,
    )

    f1, f2 = st.columns(2)
    with f1:
        sel_dept = st.multiselect(
            "Filter by department",
            sorted(doc_df["department_name"].unique().tolist()),
            default=sorted(doc_df["department_name"].unique().tolist()),
        )
    with f2:
        clinics_all = sorted(doc_df["clinic_name"].unique().tolist())
        sel_clinic = clinic_picker(clinics_all, "doc")
    doc_filt = doc_df[
        doc_df["department_name"].isin(sel_dept) &
        doc_df["clinic_name"].isin(sel_clinic)
    ]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Doctors in View",     len(doc_filt))
    k2.metric("Total Appointments",  f"{int(doc_filt['total_appointments'].sum()):,}")
    k3.metric("Avg No-Show Rate",    fmt_pct(round(doc_filt['no_show_rate_pct'].mean(), 1)) if len(doc_filt) else "—")
    wait_avg = doc_filt['avg_wait_time_minutes'].mean() if len(doc_filt) else 0
    k4.metric("Avg. Waiting Time",   fmt_min(wait_avg))
    target_caption()

    st.markdown('<p class="sec-lg">Workload vs No-Show Rate</p>', unsafe_allow_html=True)
    st.markdown('<p class="ctx">Each circle is one doctor. Bigger = more appointments. '
                'Top-right = high volume and high no-shows — the most at-risk schedule.</p>',
                unsafe_allow_html=True)

    fig = px.scatter(
        doc_filt,
        x="total_appointments", y="no_show_rate_pct",
        size="total_appointments", color="department_name",
        hover_name="doctor_name",
        hover_data={"clinic_name": True, "years_experience": True, "total_appointments": True},
        color_discrete_sequence=[C["blue"], C["orange"], C["green"], C["red"], C["purple"], "#e879f9"],
        labels={"total_appointments": "Total Appointments", "no_show_rate_pct": "No-Show Rate (%)",
                "department_name": "Department"},
    )
    fig.update_layout(**chart_base(height=380))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<p class="sec-lg">All Doctors</p>', unsafe_allow_html=True)
    st.dataframe(
        doc_filt[[
            "doctor_name", "department_name", "clinic_name",
            "years_experience", "total_appointments",
            "no_show_rate_pct", "avg_wait_time_minutes",
        ]].rename(columns={
            "doctor_name": "Doctor", "department_name": "Department",
            "clinic_name": "Clinic", "years_experience": "Experience (yrs)",
            "total_appointments": "Appointments", "no_show_rate_pct": "No-Show %",
            "avg_wait_time_minutes": "Waiting Time (min)",
        }),
        use_container_width=True, hide_index=True,
    )

# ════════════════════════════════════════════════════════════════════════
# SLA & WAIT TIMES
# ════════════════════════════════════════════════════════════════════════
elif page == "SLA & Wait Times":
    st.markdown('<p class="page-title">SLA & Wait Times</p>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="page-sub">How often do clinics see patients within '
        f'{SLA_TARGET_MIN} minutes of their scheduled time?</p>',
        unsafe_allow_html=True,
    )

    clinics_all = sorted(sla_df["clinic_name"].dropna().unique().tolist())
    sel_clinic = clinic_picker(clinics_all, "sla")
    plot_sla = sla_df[
        (sla_df["attended_appointments"] > 0) &
        sla_df["clinic_name"].isin(sel_clinic)
    ].copy()

    meeting  = int((plot_sla["sla_compliance_pct"] >= SLA_TARGET_PCT).sum())
    total_c  = len(plot_sla)
    avg_sla  = round(plot_sla["sla_compliance_pct"].mean(), 1) if total_c else 0.0
    avg_wait = round(doc_df[doc_df["clinic_name"].isin(sel_clinic)]["avg_wait_time_minutes"].mean())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Clinics Meeting SLA",    f"{meeting} / {total_c}")
    k2.metric("Network SLA Compliance", fmt_pct(avg_sla),
              delta="above target" if avg_sla >= SLA_TARGET_PCT else "below target",
              delta_color="normal" if avg_sla >= SLA_TARGET_PCT else "inverse")
    k3.metric("Average Waiting Time",   fmt_min(avg_wait))
    k4.metric("SLA Target",             f"{SLA_TARGET_MIN} min / {SLA_TARGET_PCT}%")
    target_caption()

    # Gauge + bar side by side
    gauge_col, bar_col = st.columns([4, 6])

    with gauge_col:
        st.markdown('<p class="sec-lg">Overall SLA Compliance</p>', unsafe_allow_html=True)
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=avg_sla,
            delta={"reference": SLA_TARGET_PCT, "valueformat": ".1f", "suffix": " pts vs target",
                   "increasing": {"color": C["green"]},
                   "decreasing": {"color": C["red"]},
                   "font": {"size": 13}},
            number={"suffix": "%", "font": {"color": C["text"], "size": 36}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": C["text"], "tickfont": {"color": C["text"]}},
                "bar": {"color": C["green"] if avg_sla >= SLA_TARGET_PCT else C["red"]},
                "bgcolor": C["bg"],
                "bordercolor": "#2d3048",
                "steps": [
                    {"range": [0, 60], "color": "#2d1515"},
                    {"range": [60, 80], "color": "#2d2010"},
                    {"range": [80, 100], "color": "#0d2e1a"},
                ],
                "threshold": {"line": {"color": C["green"], "width": 3},
                              "thickness": 0.75, "value": SLA_TARGET_PCT},
            },
            title={"text": f"vs {SLA_TARGET_PCT}% target", "font": {"color": "#6b7280", "size": 11}},
        ))
        fig_gauge.update_layout(
            paper_bgcolor=C["bg"], font_color=C["text"],
            height=280, margin=dict(l=20, r=20, t=30, b=10),
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

    with bar_col:
        st.markdown('<p class="sec-lg">Compliance by Clinic</p>', unsafe_allow_html=True)
        bar_colors = [
            C["green"] if v >= SLA_TARGET_PCT else C["orange"] if v >= 60 else C["red"]
            for v in plot_sla["sla_compliance_pct"]
        ]
        fig_bar = go.Figure(go.Bar(
            x=plot_sla["sla_compliance_pct"],
            y=plot_sla["clinic_name"],
            orientation="h",
            marker_color=bar_colors,
            text=plot_sla["sla_compliance_pct"].apply(lambda x: f"{x:.0f}%"),
            textposition="outside",
        ))
        fig_bar.add_vline(x=SLA_TARGET_PCT, line_dash="dash", line_color="#4b5563",
                           annotation_text=f"{SLA_TARGET_PCT}% target",
                           annotation_font_color="#6b7280",
                           annotation_position="top right")
        fig_bar.update_layout(**chart_base(
            xaxis_title="% Within 30 Minutes", yaxis_title="",
            showlegend=False,
            height=max(280, len(plot_sla) * 20),
        ))
        st.plotly_chart(fig_bar, use_container_width=True)

    # Clinic map
    map_data = plot_sla.dropna(subset=["latitude", "longitude"])
    if not map_data.empty:
        st.markdown('<p class="sec-lg">Clinic Locations — Sri Lanka</p>',
                    unsafe_allow_html=True)
        st.markdown('<p class="ctx">Circle colour shows SLA compliance. Hover for clinic name and compliance rate.</p>', unsafe_allow_html=True)
        fig_map = px.scatter_mapbox(
            map_data,
            lat="latitude", lon="longitude",
            color="sla_compliance_pct",
            size="attended_appointments",
            hover_name="clinic_name",
            hover_data={"sla_compliance_pct": True, "avg_wait_time_minutes": True},
            color_continuous_scale=[[0, C["red"]], [0.6, C["orange"]], [1, C["green"]]],
            range_color=[0, 100],
            zoom=6, height=420,
            mapbox_style="carto-darkmatter",
        )
        fig_map.update_layout(
            paper_bgcolor=C["bg"], margin=dict(l=0, r=0, t=0, b=0),
            coloraxis_colorbar=dict(
    title=dict(text="SLA %", font=dict(color=C["text"])),
    tickfont=dict(color=C["text"]),
),
        )
        st.plotly_chart(fig_map, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════
# NO-SHOW RISK PREDICTION
# ════════════════════════════════════════════════════════════════════════
elif page == "No-Show Risk Prediction":
    st.markdown('<p class="page-title">No-Show Risk Prediction</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-sub">A Random Forest model trained on 2,191 historical appointments '
        'scores each upcoming booking. Staff can prioritise reminder calls on high-risk slots '
        'before they are wasted.</p>',
        unsafe_allow_html=True,
    )

    if pred_df.empty:
        st.warning("No predictions found. Run `python scripts/train_noshow_model.py` first.")
        st.stop()

    pred_df["scheduled_date"] = pd.to_datetime(pred_df["scheduled_date"])

    # Filters
    f1, f2, f3 = st.columns(3)
    with f1:
        risk_filter = st.multiselect("Risk level", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    with f2:
        dept_filter = st.multiselect(
            "Department",
            sorted(pred_df["department_name"].dropna().unique().tolist()),
            default=sorted(pred_df["department_name"].dropna().unique().tolist()),
        )
    with f3:
        min_d, max_d = pred_df["scheduled_date"].min().date(), pred_df["scheduled_date"].max().date()
        date_sel = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
        if isinstance(date_sel, tuple) and len(date_sel) == 2:
            start_d, end_d = date_sel
        else:
            start_d, end_d = min_d, max_d

    pf = pred_df[
        pred_df["risk_label"].isin(risk_filter) &
        pred_df["department_name"].isin(dept_filter) &
        (pred_df["scheduled_date"].dt.date >= start_d) &
        (pred_df["scheduled_date"].dt.date <= end_d)
    ].copy()

    high   = int((pf["risk_label"] == "High").sum())
    medium = int((pf["risk_label"] == "Medium").sum())
    low    = int((pf["risk_label"] == "Low").sum())
    total  = len(pf)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Upcoming Appointments", total)
    k2.metric("High Risk",   high,   help="No-show probability > 60%")
    k3.metric("Medium Risk", medium, help="30–60% probability")
    k4.metric("Low Risk",    low,    help="< 30% probability")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="sec-lg">Risk Score Distribution</p>', unsafe_allow_html=True)
        fig = px.histogram(
            pf, x="no_show_probability", nbins=20,
            color="risk_label",
            color_discrete_map={"High": C["red"], "Medium": C["orange"], "Low": C["green"]},
            labels={"no_show_probability": "Predicted No-Show Probability", "risk_label": "Risk"},
        )
        fig.update_layout(**chart_base(height=270))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown('<p class="sec-lg">Risk by Department</p>', unsafe_allow_html=True)
        dr = pf.groupby(["department_name", "risk_label"]).size().reset_index(name="Count")
        fig2 = px.bar(
            dr, x="department_name", y="Count", color="risk_label",
            color_discrete_map={"High": C["red"], "Medium": C["orange"], "Low": C["green"]},
            labels={"department_name": "", "risk_label": "Risk"}, barmode="stack",
        )
        fig2.update_layout(**chart_base(height=270, xaxis_title=""))
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown('<p class="sec-lg">High Risk Appointments — Act on These First</p>',
                unsafe_allow_html=True)
    st.markdown('<p class="ctx">"Lead Days" = days between booking and appointment. '
                '"Past No-Shows" = previous missed appointments for this patient.</p>',
                unsafe_allow_html=True)

    hr = pf[pf["risk_label"] == "High"].copy()
    hr["Risk %"] = (hr["no_show_probability"] * 100).round(1)
    st.dataframe(
        hr[["appointment_id", "department_name", "scheduled_date",
            "lead_time_days", "age", "past_no_show_count", "Risk %"]]
        .rename(columns={
            "appointment_id": "Appointment ID", "department_name": "Department",
            "scheduled_date": "Date", "lead_time_days": "Lead Days",
            "age": "Patient Age", "past_no_show_count": "Past No-Shows",
        }).reset_index(drop=True),
        use_container_width=True, hide_index=True,
    )