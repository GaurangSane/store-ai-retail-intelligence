"""Simple Streamlit dashboard for the cleaned Store AI assignment project."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from insight_engine import analyze, generate_charts, get_ai_runtime_info


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
        st.image(str(path), caption=caption, width="stretch")


st.set_page_config(page_title="Store AI Dashboard", layout="wide")
st.title("Store AI Dashboard")

analysis = get_analysis()
ai_runtime = get_ai_runtime_info()

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
        analysis.product_perf[
            [
                "product_name",
                "units",
                "revenue",
                "gross_margin_rs",
                "gross_margin_pct",
                "revenue_share_pct",
            ]
        ].rename(
            columns={
                "product_name": "Product",
                "units": "Units",
                "revenue": "Revenue (Rs.)",
                "gross_margin_rs": "Gross Margin (Rs.)",
                "gross_margin_pct": "Gross Margin (%)",
                "revenue_share_pct": "Revenue Share (%)",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    st.caption("Gross margin uses product cost and is not net profit.")

with tabs[2]:
    st.subheader("Inventory & Sizes")
    show_chart(CHART_DIR / "size_demand.png", "Demand by size")
    st.dataframe(
        analysis.size_inventory[["size", "units", "revenue", "stockout_sku_days", "ending_stock", "days_of_cover"]],
        width="stretch",
        hide_index=True,
    )
    st.subheader("Inventory Movement Check")
    st.write("Expected closing = opening stock + received stock + returns + adjustments - sold units.")
    st.dataframe(
        analysis.inventory_movement.rename(
            columns={
                "opening_stock": "Opening Stock",
                "stock_received": "Received Stock",
                "returns": "Returns",
                "adjustments": "Adjustments",
                "quantity_sold": "Sold Units",
                "expected_closing": "Expected Closing",
                "closing_stock": "Closing Stock",
                "reconciliation_difference": "Reconciliation Difference",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    st.caption("Returns and adjustments are included explicitly in stock movement.")

with tabs[3]:
    st.subheader("Trading Days")
    show_chart(CHART_DIR / "weekday_revenue.png", "Average revenue per trading day")
    st.dataframe(analysis.weekday_perf, width="stretch", hide_index=True)

with tabs[4]:
    st.subheader("Customer Patterns")
    st.dataframe(
        analysis.customer_patterns.rename(
            columns={
                "segment": "Segment",
                "category": "Category",
                "segment_share_pct": "Segment Share %",
                "store_share_pct": "Store Share %",
                "lift": "Lift",
                "support_units": "Support Units",
                "business_meaning": "Business Meaning",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    st.caption("These are simulated monthly patterns and not real demographic claims.")

with tabs[5]:
    st.subheader("AI Manager Actions")
    st.write(f"Model used: {ai_runtime['model']} via {ai_runtime['provider']}")
    st.caption("Python calculates all numbers; AI only explains verified facts.")
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
