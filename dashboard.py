"""Simple Streamlit dashboard for the cleaned Store AI assignment project."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from insight_engine import analyze, generate_charts


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CHART_DIR = OUTPUT_DIR / "charts"


@st.cache_data
def get_analysis():
    analysis = analyze()
    generate_charts(analysis)
    return analysis


def show_chart(path: Path, caption: str) -> None:
    if path.exists():
        st.image(str(path), caption=caption, use_container_width=True)


st.set_page_config(page_title="Store AI Dashboard", layout="wide")
st.title("Store AI Dashboard")

analysis = get_analysis()

tabs = st.tabs(
    [
        "Overview",
        "Product Performance",
        "Inventory & Sizes",
        "Trading Days",
        "Customer Patterns",
        "AI Manager Actions",
        "Final Report",
    ]
)

with tabs[0]:
    cols = st.columns(4)
    cols[0].metric("Revenue", f"Rs. {analysis.kpis['total_revenue']:,.0f}")
    cols[1].metric("Units Sold", f"{analysis.kpis['total_units']:,}")
    cols[2].metric("Invoices", f"{analysis.kpis['transactions']:,}")
    cols[3].metric("Average Bill", f"Rs. {analysis.kpis['average_bill_value']:,.0f}")
    st.write(f"Period analysed: {analysis.kpis['date_start']} to {analysis.kpis['date_end']}")
    st.write(
        f"Highest revenue date: {analysis.kpis['highest_revenue_date']} "
        f"with Rs. {analysis.kpis['highest_revenue_date_sales']:,.0f}"
    )

with tabs[1]:
    st.subheader("Product Performance")
    show_chart(CHART_DIR / "product_units.png", "Top products by units sold")
    st.dataframe(
        analysis.product_perf[["product_name", "units", "revenue", "gross_margin_rs", "revenue_share_pct"]],
        use_container_width=True,
        hide_index=True,
    )

with tabs[2]:
    st.subheader("Inventory & Sizes")
    show_chart(CHART_DIR / "size_demand.png", "Demand by size")
    st.dataframe(
        analysis.size_inventory[["size", "units", "revenue", "stockout_sku_days", "ending_stock", "days_of_cover"]],
        use_container_width=True,
        hide_index=True,
    )

with tabs[3]:
    st.subheader("Trading Days")
    show_chart(CHART_DIR / "weekday_revenue.png", "Average revenue per trading day")
    st.dataframe(analysis.weekday_perf, use_container_width=True, hide_index=True)

with tabs[4]:
    st.subheader("Customer Patterns")
    st.dataframe(analysis.customer_patterns, use_container_width=True, hide_index=True)
    st.caption("These are simulated assignment patterns and should not be generalized to real Pune shoppers.")

with tabs[5]:
    st.subheader("AI Manager Actions")
    for index, action in enumerate(analysis.actions, start=1):
        st.write(f"{index}. {action}")
    ai_path = OUTPUT_DIR / "ai_manager_insights.md"
    if ai_path.exists():
        st.markdown(ai_path.read_text(encoding="utf-8"))

with tabs[6]:
    st.subheader("Final Report")
    report_path = OUTPUT_DIR / "store_report.md"
    pdf_path = OUTPUT_DIR / "store_report.pdf"
    if report_path.exists():
        st.markdown(report_path.read_text(encoding="utf-8"))
    else:
        st.info("Run `python insight_engine.py` to generate the final report.")
    if pdf_path.exists():
        st.download_button("Download PDF report", pdf_path.read_bytes(), file_name="store_report.pdf", mime="application/pdf")
