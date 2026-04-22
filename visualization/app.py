import json
import re
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# --- System & Setup ---
_VN_TZ = timezone(timedelta(hours=7))

st.set_page_config(
    page_title="Data/System Audit Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .reportview-container .main .block-container{
        max-width: 1400px;
        padding-top: 1rem;
    }
    .metric-card {
        background-color: #f1f3f6;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        text-align: center;
    }
    .metric-value {
        font-size: 2.2rem;
        color: #1a73e8;
        font-weight: bold;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 6px 6px 0px 0px;
        gap: 5px;
        padding: 10px 20px;
        font-weight: bold;
        font-size: 1.1rem;
    }
    .stTabs [aria-selected="true"] {
        background-color: #f0f8ff;
        border-bottom: 3px solid #1a73e8;
        color: #1a73e8;
    }
    .markdown-report {
        background-color: transparent;
        padding: 20px 40px;
        color: inherit;
        line-height: 1.6;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    .markdown-report h1, .markdown-report h2, .markdown-report h3 {
        color: #1a73e8;
        border-bottom: 1px solid #f0f0f0;
        padding-bottom: 8px;
        margin-top: 24px;
    }
    .markdown-report table {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
    }
    .markdown-report th, .markdown-report td {
        padding: 12px;
        border: 1px solid #ddd;
        text-align: left;
    }
    .markdown-report th {
        background-color: rgba(128, 128, 128, 0.1);
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- Data Extraction Definitions ---
class AuditDataExtractor:
    def __init__(self, logs_dir: str = "../logs", raw_dir: str = "../storage/raw", reports_dir: str = "../storage/reports",
                 ai_results_dir: str = "../storage/ai_results", ab_results_dir: str = "../storage/ab_results",
                 test_results_dir: str = "../storage/test_results"):
        self.logs_dir = Path(logs_dir)
        self.raw_dir = Path(raw_dir)
        self.reports_dir = Path(reports_dir)
        self.ai_results_dir = Path(ai_results_dir)
        self.ab_results_dir = Path(ab_results_dir)
        self.test_results_dir = Path(test_results_dir)

    def get_available_dates(self) -> list[str]:
        """Get list of dates with raw data and system logs."""
        dates = set()
        
        # Get from raw directory
        if self.raw_dir.exists():
            for json_file in self.raw_dir.glob("*.json"):
                parts = json_file.stem.split('_')
                if len(parts) >= 1 and re.match(r"\d{4}-\d{2}-\d{2}", parts[0]):
                    dates.add(parts[0])

        # Get from logs directory path (logs/MM-YYYY/DD/)
        if self.logs_dir.exists():
            for sub_logs in self.logs_dir.rglob("*.log.json"):
                parts = sub_logs.parts
                # Check structure 04-2026/21
                if len(parts) >= 3:
                    month_yr = parts[-3]
                    day = parts[-2]
                    if re.match(r"\d{2}-\d{4}", month_yr) and re.match(r"\d{2}", day):
                        y, m = month_yr.split('-')[1], month_yr.split('-')[0]
                        dates.add(f"{y}-{m}-{day}")

        return sorted(list(dates), reverse=True)

    def extract_merge_metrics(self, target_date: str = "All") -> pd.DataFrame:
        records = []
        if not self.raw_dir.exists(): return pd.DataFrame()

        pattern = f"{target_date}_*.json" if target_date != "All" else "*.json"
        
        for json_file in sorted(self.raw_dir.glob(pattern)):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("metadata", {})
                source = meta.get("source", "unknown")
                total = meta.get("total_articles", 0)
                stats = meta.get("stats", {})
                records.append({
                    "date": json_file.stem.split('_')[0],
                    "source": source,
                    "total": total,
                    "new": stats.get("new", 0),
                    "updated": stats.get("updated", 0),
                    "deduped": stats.get("deduped", 0)
                })
            except Exception:
                continue

        df = pd.DataFrame(records)
        if not df.empty:
            df = df.groupby("source", as_index=False).sum(numeric_only=True)
        return df

    def extract_field_health(self, target_date: str = "All") -> pd.DataFrame:
        check_fields = ["title", "content", "publish_date", "title_hash", "content_hash", "article_id", "url"]
        records = []
        if not self.raw_dir.exists(): return pd.DataFrame()

        pattern = f"{target_date}_*.json" if target_date != "All" else "*.json"
        source_data = {}

        for json_file in sorted(self.raw_dir.glob(pattern)):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                articles = data.get("articles", [])
                source = data.get("metadata", {}).get("source", "unknown")
                
                if source not in source_data:
                    source_data[source] = {"total": 0, "fields": {f: 0 for f in check_fields}}
                
                source_data[source]["total"] += len(articles)
                for field in check_fields:
                    non_null = sum(1 for a in articles if a.get(field) is not None and str(a.get(field)).strip() != "")
                    source_data[source]["fields"][field] += non_null
            except Exception:
                continue

        for source, sdata in source_data.items():
            total = sdata["total"]
            if total == 0: continue
            row = {"source": source}
            for field in check_fields:
                row[field] = round((sdata["fields"][field] / total) * 100, 1)
            records.append(row)
            
        return pd.DataFrame(records)

    def extract_error_metrics(self, target_date: str = "All") -> pd.DataFrame:
        """Scan all error logs and use timestamp to get the correct date."""
        records = []
        if not self.logs_dir.exists(): return pd.DataFrame()

        error_files = list(self.logs_dir.rglob("*_errors.log.json"))
        curr = self.logs_dir / "current_errors.log.json"
        if curr.exists() and curr not in error_files:
            error_files.append(curr)

        seen_logs = set()
        for error_file in error_files:
            try:
                with open(error_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip(): continue
                        try:
                            entry = json.loads(line.strip())
                            ts = entry.get("timestamp", "")
                            if target_date != "All" and not ts.startswith(target_date):
                                continue
                                
                            msg = entry.get("message", "")
                            log_id = f"{ts}-{msg}"
                            if log_id in seen_logs: continue
                            seen_logs.add(log_id)
                            
                            logger_name = entry.get("logger", "")
                            source = "unknown"
                            for s in ["vnexpress", "thanhnien", "tuoitre"]:
                                if s in logger_name:
                                    source = s; break
                            
                            error_type = "Other"
                            if "Content too short" in msg: error_type = "Content_Too_Short"
                            elif "No articles found" in msg: error_type = "No_Articles_Found"
                            elif "Date Parse FAILURE" in msg: error_type = "Date_Parse_Failure"
                            elif "Request failed" in msg: error_type = "Request_Failed"
                            elif "Failed to extract title" in msg: error_type = "Title_Missing"

                            records.append({
                                "timestamp": ts,
                                "source": source,
                                "error_type": error_type,
                                "level": entry.get("level", "WARNING"),
                                "module": entry.get("module", ""),
                                "message": msg[:200],
                            })
                        except Exception:
                            pass
            except Exception:
                continue
        
        df = pd.DataFrame(records)
        return df

    def extract_system_logs_timeline(self, target_date: str = "All") -> pd.DataFrame:
        """Find all system log events (INFO/WARNING/ERROR) to create a timeline."""
        records = []
        if not self.logs_dir.exists(): return pd.DataFrame()

        log_files = []
        for f in self.logs_dir.rglob("*.log.json"):
            if "_errors" not in f.name and "current_" not in f.name:
                log_files.append(f)
        
        curr = self.logs_dir / "current_run.log.json"
        if curr.exists() and curr not in log_files:
            log_files.append(curr)

        seen_logs = set()
        for log_file in log_files:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip(): continue
                        try:
                            entry = json.loads(line.strip())
                            ts = entry.get("timestamp", "")
                            if target_date != "All" and not ts.startswith(target_date):
                                continue
                                
                            lvl = entry.get("level", "INFO")
                            msg = entry.get("message", "")
                            log_id = f"{ts}-{msg}"
                            if log_id in seen_logs: continue
                            seen_logs.add(log_id)
                            records.append({"timestamp": ts, "level": lvl})
                        except:
                            pass
            except:
                continue
                
        df = pd.DataFrame(records)
        if not df.empty:
            df["time"] = pd.to_datetime(df["timestamp"]).dt.strftime('%H:%M')
            grouped = df.groupby(["time", "level"]).size().reset_index(name="count")
            return grouped
        return df

    def get_available_reports(self) -> list[str]:
        """Get list of markdown report files."""
        if not self.reports_dir.exists(): return []
        reports = [f.name for f in self.reports_dir.glob("*.md")]
        return sorted(reports, reverse=True)

    def read_report(self, report_name: str) -> tuple[str, bool]:
        """Read markdown content and check if an accompanying PDF file exists."""
        if not report_name: return "", False
        md_file = self.reports_dir / report_name
        pdf_file = self.reports_dir / report_name.replace(".md", ".pdf")
        
        content = ""
        if md_file.exists():
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
                
        return content, pdf_file.exists()

    def load_ai_results(self) -> list[dict]:
        """Load all AI analysis results from storage/ai_results/."""
        results = []
        if not self.ai_results_dir.exists(): return results
        for f in sorted(self.ai_results_dir.glob("*.json"), reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    data["_filename"] = f.name
                    results.append(data)
            except Exception:
                continue
        return results

    def load_ab_results(self) -> list[dict]:
        """Load all A/B Testing results from storage/ab_results/."""
        results = []
        if not self.ab_results_dir.exists(): return results
        for f in sorted(self.ab_results_dir.glob("*.json"), reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    results.append(json.load(fp))
            except Exception:
                continue
        return results

    def extract_test_results(self) -> dict:
        """Extract results from pytest (XML) and coverage (JSON)."""
        coverage_data = {}
        test_summary = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0}
        
        # 1. Load Coverage JSON
        cov_file = self.test_results_dir / "coverage.json"
        if cov_file.exists():
            try:
                with open(cov_file, "r", encoding="utf-8") as f:
                    raw_cov = json.load(f)
                    files_cov = raw_cov.get("files", {})
                    for filepath, data in files_cov.items():
                        module_name = filepath.replace("\\", "/")
                        coverage_data[module_name] = round(data.get("summary", {}).get("percent_covered", 0), 1)
                coverage_data["TOTAL"] = round(raw_cov.get("totals", {}).get("percent_covered", 0), 1)
            except Exception:
                pass

        # 2. Load JUnit XML
        xml_file = self.test_results_dir / "tests.xml"
        if xml_file.exists():
            try:
                with open(xml_file, "r", encoding="utf-8") as f:
                    xml_content = f.read()
                import re
                tests_match = re.search(r'tests="(\d+)"', xml_content)
                failures_match = re.search(r'failures="(\d+)"', xml_content)
                errors_match = re.search(r'errors="(\d+)"', xml_content)
                skipped_match = re.search(r'skipped="(\d+)"', xml_content)
                if tests_match:
                    total = int(tests_match.group(1))
                    failures = int(failures_match.group(1)) if failures_match else 0
                    errors = int(errors_match.group(1)) if errors_match else 0
                    skipped = int(skipped_match.group(1)) if skipped_match else 0
                    test_summary = {
                        "total": total,
                        "passed": total - failures - errors - skipped,
                        "failed": failures,
                        "skipped": skipped,
                        "errors": errors
                    }
            except Exception:
                pass
        return {"coverage": coverage_data, "summary": test_summary}

# --- Initialize Extractor & Logic ---
base_dir = Path(__file__).resolve().parent.parent
logs_dir = base_dir / "logs"
raw_dir = base_dir / "storage" / "raw"
reports_dir = base_dir / "storage" / "reports"
ai_results_dir = base_dir / "storage" / "ai_results"
ab_results_dir = base_dir / "storage" / "ab_results"
extractor = AuditDataExtractor(
    logs_dir=str(logs_dir), raw_dir=str(raw_dir), reports_dir=str(reports_dir),
    ai_results_dir=str(ai_results_dir), ab_results_dir=str(ab_results_dir),
    test_results_dir=str(base_dir / "storage" / "test_results")
)

# --- Sidebar ---
st.sidebar.title("📅 Data History")
st.sidebar.markdown("Select a time to view the audit report.")

available_dates = extractor.get_available_dates()
date_options = ["All"] + available_dates

selected_date = st.sidebar.selectbox("Crawl Date", date_options)

st.sidebar.divider()
st.sidebar.caption("Visualization based on RAW Storage and 100% History System Logs. If a day has no data, the charts will elegantly show No Data.")

st.sidebar.divider()
st.sidebar.title("📝 Automated Reports")
st.sidebar.markdown("Select an AI analysis report to view.")
available_reports = extractor.get_available_reports()
selected_report = st.sidebar.selectbox("Markdown Reports", available_reports) if available_reports else None

# --- Data Loading (Cache) ---
@st.cache_data(ttl=15, show_spinner=False)
def load_data(date_filter: str):
    return {
        "merge_df": extractor.extract_merge_metrics(date_filter),
        "health_df": extractor.extract_field_health(date_filter),
        "error_df": extractor.extract_error_metrics(date_filter),
        "timeline_df": extractor.extract_system_logs_timeline(date_filter),
        "test_results": extractor.extract_test_results(),
    }

with st.spinner("Extracting entire system history..."):
    data = load_data(selected_date)

merge_df = data["merge_df"]
health_df = data["health_df"]
error_df = data["error_df"]
timeline_df = data["timeline_df"]

# --- Render UI Top Header ---
st.title(f"📈 Master System Audit Dashboard ({selected_date})")
total_articles = merge_df["total"].sum() if not merge_df.empty else 0
st.markdown(f"**Total RAW articles in DB:** `{total_articles}`")
st.divider()

# --- TABS LAYOUT ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Data Overview", 
    "📉 System & Errors",
    "📝 AI Reports",
    "🤖 AI Insights",
    "🧪 A/B Testing",
    "✅ Automated Testing",
])

# ----------------- TAB 1: DATA STORAGE -----------------
with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🌐 Sources & Crawl Funnel")
        if merge_df.empty:
            st.info(f"No crawl data for selection '{selected_date}'.")
        else:
            plot_df = merge_df.melt(id_vars=["source"], value_vars=["new", "updated", "deduped"], 
                                    var_name="Type", value_name="Count")
            color_map = {"new": "#2196F3", "updated": "#FF9800", "deduped": "#9E9E9E"}
            fig_funnel = px.bar(plot_df, x="source", y="Count", color="Type", 
                                color_discrete_map=color_map, text="Count")
            fig_funnel.update_traces(textposition='inside')
            st.plotly_chart(fig_funnel, width="stretch")

    with col2:
        st.subheader("🏥 Data Health (% Not Null)")
        if health_df.empty:
            st.info("No data available for field health assessment.")
        else:
            plot_df = health_df.set_index("source")
            fig_heat = px.imshow(plot_df, text_auto=True, color_continuous_scale="RdYlGn",
                                 zmin=0, zmax=100)
            fig_heat.update_coloraxes(showscale=False)
            fig_heat.update_layout(margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_heat, width="stretch")

# ----------------- TAB 2: SYSTEM LOGS -----------------
with tab2:
    col3, col4 = st.columns([2, 1])
    
    with col3:
        st.subheader("⏱️ System Pace (Log Timeline)")
        if timeline_df.empty:
            st.info("No activity history (INFO/WARNING) to draw timeline.")
        else:
            color_map = {"INFO": "#2196F3", "WARNING": "#FF9800", "ERROR": "#F44336"}
            fig_line = px.bar(timeline_df, x="time", y="count", color="level", 
                               title="Log events over time (grouped by minute)",
                               color_discrete_map=color_map)
            st.plotly_chart(fig_line, width="stretch")
            
    with col4:
        st.subheader("🔍 System Error Patterns")
        if error_df.empty:
            st.success("✅ Great! No error patterns detected during this period.")
        else:
            counts = error_df["error_type"].value_counts().reset_index()
            counts.columns = ["Error Type", "Count"]
            fig_error = px.pie(counts, values='Count', names='Error Type', hole=0.5,
                               color_discrete_sequence=px.colors.qualitative.Set3)
            fig_error.update_traces(textposition='inside', textinfo='percent')
            fig_error.update_layout(margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_error, width="stretch")

    st.subheader("📑 Error/Warning Details")
    if not error_df.empty:
        # Filter display
        st.dataframe(
            error_df[["timestamp", "level", "source", "module", "error_type", "message"]].sort_values("timestamp", ascending=False),
            width="stretch",
            hide_index=True
        )
    else:
        st.markdown("<div style='text-align: center; color: gray; padding: 20px;'>--- Empty Error Log ---</div>", unsafe_allow_html=True)

# ----------------- TAB 3: AI REPORT -----------------
with tab3:
    if not selected_report:
        st.info("No static reports found in 'storage/reports'. Please run the Pipeline to generate AI reports first.")
    else:
        st.subheader(f"📄 Detailed Report: {selected_report}")
        report_content, has_pdf = extractor.read_report(selected_report)
        
        col_actions, col_space = st.columns([1, 4])
        with col_actions:
            if has_pdf:
                pdf_path = extractor.reports_dir / selected_report.replace(".md", ".pdf")
                with open(pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="⬇️ Download PDF Print",
                        data=pdf_file,
                        file_name=selected_report.replace(".md", ".pdf"),
                        mime="application/pdf",
                        type="primary"
                    )
            else:
                st.button("⬇️ PDF Not Available", disabled=True)
                
        st.markdown("<hr/>", unsafe_allow_html=True)
        
        # Wrap markdown in HTML Container with CSS
        st.markdown(f'<div class="markdown-report">{report_content}</div>', unsafe_allow_html=True)

# ----------------- TAB 4: AI INSIGHTS -----------------
with tab4:
    ai_results = extractor.load_ai_results()
    if not ai_results:
        st.info("No AI analysis data available. Run `python main.py --step analyze` first.")
    else:
        latest = ai_results[0]
        
        # --- Metadata Metrics ---
        st.subheader("⚙️ AI Processing Session Info")
        m1, m2, m3 = st.columns(3)
        m1.metric("Model Used", latest.get("model_used", "N/A"))
        m2.metric("Fallback Triggered?", "Yes ⚠️" if latest.get("fallback_triggered") else "No ✅")
        ts_raw = latest.get("processing_timestamp", "")
        ts_display = ts_raw[:19] if ts_raw else "N/A"
        m3.metric("Processing Time", ts_display)
        
        st.divider()
        
        col_kw, col_cat = st.columns([3, 2])
        
        # --- Keywords Bar Chart ---
        with col_kw:
            st.subheader("🔑 Top Trending Keywords")
            keywords = latest.get("trending_keywords", [])
            if keywords:
                kw_df = pd.DataFrame(keywords)
                kw_df = kw_df.sort_values("frequency", ascending=True)
                fig_kw = px.bar(kw_df, x="frequency", y="keyword", orientation="h",
                                color="category",
                                color_discrete_sequence=px.colors.qualitative.Set2,
                                text="frequency")
                fig_kw.update_layout(height=500, margin=dict(l=20, r=20, t=20, b=20),
                                     yaxis_title="", xaxis_title="Frequency")
                fig_kw.update_traces(textposition='outside')
                st.plotly_chart(fig_kw, width='stretch')
            else:
                st.info("No keyword data available.")
        
        # --- Category Pie Chart ---
        with col_cat:
            st.subheader("📂 Category Distribution")
            if keywords:
                cat_df = kw_df.groupby("category", as_index=False)["frequency"].sum()
                fig_cat = px.pie(cat_df, values="frequency", names="category", hole=0.45,
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_cat.update_traces(textposition='inside', textinfo='percent+label')
                fig_cat.update_layout(height=500, margin=dict(l=20, r=20, t=20, b=20),
                                      showlegend=False)
                st.plotly_chart(fig_cat, width='stretch')
            else:
                st.info("No category data available.")
        
        st.divider()
        
        # --- Highlighted News Table ---
        st.subheader("⭐ Highlighted News (AI-selected)")
        highlights = latest.get("highlighted_news", [])
        if highlights:
            for i, h in enumerate(highlights, 1):
                score = h.get("relevance_score", 0)
                col_rank, col_info, col_bar = st.columns([0.5, 5, 2])
                with col_rank:
                    st.markdown(f"### {i}")
                with col_info:
                    st.markdown(f"**{h.get('title', 'N/A')}**")
                    st.caption(f"📰 {h.get('source', 'N/A')} — {h.get('summary', '')[:150]}...")
                with col_bar:
                    st.progress(score, text=f"Relevance: {score:.0%}")
                st.divider()
        else:
            st.info("No highlighted news data.")

# ----------------- TAB 5: A/B TESTING -----------------
with tab5:
    ab_results = extractor.load_ab_results()
    if not ab_results:
        st.info("No A/B Testing results available. Run: `python -m tests.ab_testing.run_ab_test --list` to see available tests.")
    else:
        st.subheader("🧪 A/B Testing History")
        
        # --- Summary Table ---
        table_rows = []
        for r in ab_results:
            table_rows.append({
                "Experiment": r.get("experiment_name", "N/A"),
                "Variant A": r.get("variant_a_name", "N/A"),
                "Score A": r.get("variant_a_score", 0),
                "Latency A (ms)": r.get("variant_a_latency_ms", 0),
                "Variant B": r.get("variant_b_name", "N/A"),
                "Score B": r.get("variant_b_score", 0),
                "Latency B (ms)": r.get("variant_b_latency_ms", 0),
                "🏆 Winner": r.get("winner", "N/A"),
                "Margin": r.get("margin", 0),
                "Verdict": r.get("verdict", "N/A"),
                "Timestamp": r.get("timestamp", "N/A")[:19],
            })
        
        ab_df = pd.DataFrame(table_rows)
        st.dataframe(ab_df, width='stretch', hide_index=True)
        
        st.divider()
        
        # --- Score Comparison Bar Chart ---
        st.subheader("📊 Score Comparison (Score A vs Score B)")
        chart_data = []
        for r in ab_results:
            exp = r.get("experiment_name", "N/A")
            chart_data.append({"Experiment": exp, "Variant": r.get("variant_a_name", "A"), "Score": r.get("variant_a_score", 0)})
            chart_data.append({"Experiment": exp, "Variant": r.get("variant_b_name", "B"), "Score": r.get("variant_b_score", 0)})
        
        chart_df = pd.DataFrame(chart_data)
        fig_ab = px.bar(chart_df, x="Experiment", y="Score", color="Variant",
                        barmode="group", text="Score",
                        color_discrete_sequence=["#2196F3", "#FF9800"])
        fig_ab.update_traces(textposition='outside')
        fig_ab.update_layout(yaxis_range=[0, 105], margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_ab, width='stretch')
        
        # --- Latency Comparison ---
        st.subheader("⏱️ Latency Comparison (Latency ms)")
        lat_data = []
        for r in ab_results:
            exp = r.get("experiment_name", "N/A")
            lat_data.append({"Experiment": exp, "Variant": r.get("variant_a_name", "A"), "Latency (ms)": r.get("variant_a_latency_ms", 0)})
            lat_data.append({"Experiment": exp, "Variant": r.get("variant_b_name", "B"), "Latency (ms)": r.get("variant_b_latency_ms", 0)})
        
        lat_df = pd.DataFrame(lat_data)
        fig_lat = px.bar(lat_df, x="Experiment", y="Latency (ms)", color="Variant",
                         barmode="group", text="Latency (ms)",
                         color_discrete_sequence=["#4CAF50", "#E91E63"])
        fig_lat.update_traces(textposition='outside', texttemplate='%{text:.0f}ms')
        fig_lat.update_layout(margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_lat, width='stretch')

# ----------------- TAB 6: AUTOMATION TESTS -----------------
with tab6:
    test_data = data.get("test_results", {})
    summary = test_data.get("summary", {})
    coverage = test_data.get("coverage", {})

    if not summary or summary.get("total") == 0:
        st.info("No Automation Test results. Please run `pytest` and export results first.")
    else:
        st.subheader("🧪 Test Results Summary")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total tests", summary.get("total", 0))
        c2.markdown(f"<div class='metric-card'><div style='color:green'>Pass</div><div class='metric-value'>{summary.get('passed', 0)}</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='metric-card'><div style='color:red'>Fail</div><div class='metric-value'>{summary.get('failed', 0)}</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='metric-card'><div style='color:orange'>Skip</div><div class='metric-value'>{summary.get('skipped', 0)}</div></div>", unsafe_allow_html=True)
        c5.markdown(f"<div class='metric-card'><div style='color:#1a73e8'>Coverage</div><div class='metric-value'>{coverage.get('TOTAL', 0)}%</div></div>", unsafe_allow_html=True)

        st.divider()

        col_cov, col_pie = st.columns([3, 2])

        with col_cov:
            st.subheader("📊 Code Coverage (Coverage per Module)")
            cov_plot = {k: v for k, v in coverage.items() if k != "TOTAL"}
            if cov_plot:
                df_cov = pd.DataFrame(list(cov_plot.items()), columns=["Module", "Coverage (%)"])
                df_cov = df_cov.sort_values("Coverage (%)", ascending=True)
                fig_cov = px.bar(df_cov, x="Coverage (%)", y="Module", orientation="h",
                                 color="Coverage (%)", color_continuous_scale="RdYlGn",
                                 range_x=[0, 100], text="Coverage (%)")
                fig_cov.update_layout(margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_cov, width='stretch')
            else:
                st.info("No detailed coverage data available.")

        with col_pie:
            st.subheader("🎯 Status Ratio")
            df_pie = pd.DataFrame({
                "Status": ["Passed", "Failed", "Skipped", "Errors"],
                "Count": [summary.get("passed", 0), summary.get("failed", 0), 
                          summary.get("skipped", 0), summary.get("errors", 0)]
            })
            # Filter out zero statuses for a cleaner pie chart
            df_pie = df_pie[df_pie["Count"] > 0]
            if not df_pie.empty:
                fig_pie = px.pie(df_pie, values="Count", names="Status", hole=0.4,
                                 color="Status",
                                 color_discrete_map={"Passed": "#4CAF50", "Failed": "#F44336", 
                                                     "Skipped": "#FF9800", "Errors": "#9C27B0"})
                fig_pie.update_layout(margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_pie, width='stretch')
            else:
                st.info("No data available to draw pie chart.")
