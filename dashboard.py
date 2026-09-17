"""Manager-friendly Streamlit dashboard for the Store AI assignment."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from insight_engine import analyze, analyze_from_frames, generate_outputs, missing_product_skus


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CHART_DIR = OUTPUT_DIR / "charts"


def read_upload(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    return pd.read_csv(BytesIO(uploaded_file.getvalue()))


def show_chart(path: Path, caption: str) -> None:
    if path.exists():
        st.image(str(path), caption=caption, width="stretch")


def save_dashboard_run(analysis, mode: str, sources: dict[str, str]) -> None:
    explanation, ai_runtime = generate_outputs(analysis)
    st.session_state["analysis"] = analysis
    st.session_state["mode"] = mode
    st.session_state["sources"] = sources
    st.session_state["manager_explanation"] = explanation
    st.session_state["ai_runtime"] = ai_runtime
    st.session_state["missing_skus"] = missing_product_skus(analysis.sales, analysis.products)


st.set_page_config(page_title="Store AI Dashboard", layout="wide")
st.title("Store AI Dashboard")
st.caption("Monthly retail decisions from sales, product, and inventory data")

with st.sidebar:
    st.header("Monthly files")
    sales_upload = st.file_uploader(
        "Monthly sales_data.csv",
        type=["csv"],
        help="Leave empty to use the included sample month.",
    )
    with st.expander("Advanced optional files"):
        product_upload = st.file_uploader(
            "product_master.csv (optional)",
            type=["csv"],
            help="Upload only when the product reference changed.",
        )
        inventory_upload = st.file_uploader(
            "inventory_daily.csv (optional)",
            type=["csv"],
            help="Upload only when the inventory reference changed.",
        )
    run_clicked = st.button("Run Analysis", type="primary", width="stretch")
    st.caption("Product and inventory files silently reuse the included defaults when omitted.")

if "analysis" not in st.session_state:
    try:
        with st.spinner("Loading the default sample month..."):
            save_dashboard_run(
                analyze(),
                "Default sample month",
                {"Sales": "default", "Product master": "default", "Inventory": "default"},
            )
    except Exception:
        st.error("The default analysis could not be generated. Check the included CSV files.")
        st.stop()

if run_clicked:
    try:
        sales_frame = read_upload(sales_upload)
        product_frame = read_upload(product_upload)
        inventory_frame = read_upload(inventory_upload)
        with st.spinner("Running monthly analysis and regenerating the report..."):
            analysis_result = analyze_from_frames(
                sales_df=sales_frame,
                products_df=product_frame,
                inventory_df=inventory_frame,
            )
            save_dashboard_run(
                analysis_result,
                "Uploaded sales month" if sales_frame is not None else "Default sample month",
                {
                    "Sales": "uploaded" if sales_frame is not None else "default",
                    "Product master": "uploaded" if product_frame is not None else "default",
                    "Inventory": "uploaded" if inventory_frame is not None else "default",
                },
            )
        st.success("Analysis and report regenerated.")
    except (ValueError, pd.errors.ParserError) as exc:
        st.error(f"Could not run analysis: {exc}")
    except Exception:
        st.error("The analysis could not be completed. Check the uploaded CSV format and try again.")

analysis = st.session_state["analysis"]
ai_runtime = st.session_state["ai_runtime"]
sources = st.session_state["sources"]

st.info(
    f"**Current mode: {st.session_state['mode']}**  \n"
    f"Sales: {sources['Sales']} · Product master: {sources['Product master']} · "
    f"Inventory: {sources['Inventory']}"
)
if sales_upload is not None and st.session_state["mode"] != "Uploaded sales month":
    st.caption("A sales file is selected. Choose Run Analysis to apply it.")
if st.session_state["mode"] == "Uploaded sales month" and st.session_state["missing_skus"]:
    st.warning("Some SKUs are not present in product master; margin/inventory metrics may be partial.")
if sources["Sales"] == "uploaded" and analysis.kpis.get("inventory_date_warning"):
    st.warning(analysis.kpis["inventory_date_warning"])

tabs = st.tabs(
    [
        "Overview",
        "Product Performance",
        "Inventory & Sizes",
        "Reorder Priority",
        "Slow Stock / Markdown Priority",
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
            ["product_name", "units", "revenue", "gross_margin_rs", "gross_margin_pct", "manager_interpretation"]
        ].rename(
            columns={
                "product_name": "Product",
                "units": "Units",
                "revenue": "Revenue (Rs.)",
                "gross_margin_rs": "Gross Margin (Rs.)",
                "gross_margin_pct": "Gross Margin (%)",
                "manager_interpretation": "Manager Interpretation",
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
        analysis.size_inventory[
            ["size", "units", "revenue", "stockout_sku_days", "ending_stock", "days_of_cover"]
        ],
        width="stretch",
        hide_index=True,
    )
    st.subheader("Inventory Movement Check")
    st.write("Expected closing = opening stock + received stock + returns + adjustments - sold units.")
    st.dataframe(analysis.inventory_movement, width="stretch", hide_index=True)

with tabs[3]:
    st.subheader("Reorder Priority")
    st.caption("Recent daily velocity uses the last 7 calendar days in the sales month.")
    st.dataframe(analysis.reorder_priority, width="stretch", hide_index=True)

with tabs[4]:
    st.subheader("Slow Stock / Markdown Priority")
    st.info("Review display/price first; markdown only if stock remains slow.")
    st.dataframe(analysis.slow_stock_priority, width="stretch", hide_index=True)

with tabs[5]:
    st.subheader("Trading Days")
    show_chart(CHART_DIR / "weekday_revenue.png", "Average revenue per trading day")
    st.dataframe(analysis.weekday_perf, width="stretch", hide_index=True)
    st.caption(
        "Any Tuesday offer is a controlled test with margin tracking; the dashboard does not assume it will increase sales."
    )

with tabs[6]:
    st.subheader("Customer Patterns")
    st.dataframe(analysis.customer_patterns, width="stretch", hide_index=True)
    if analysis.customer_summary:
        for sentence in analysis.customer_summary:
            st.write(f"- {sentence}")
    else:
        st.write("No lift pattern met the minimum support threshold for this sales file.")
    st.caption("These are merchandising test signals, not demographic truth.")

with tabs[7]:
    st.subheader("AI Manager Actions")
    st.write(f"Model metadata: {ai_runtime['model']} via {ai_runtime['provider']}")
    st.caption("Python calculates all numbers and exactly three actions. AI only provides a short interpretation.")
    st.write(st.session_state["manager_explanation"])
    st.subheader("Exactly 3 Actions for Next Week")
    for index, action in enumerate(analysis.actions, start=1):
        st.write(f"{index}. {action}")

with tabs[8]:
    st.subheader("Final Report")
    report_path = OUTPUT_DIR / "store_report.md"
    pdf_path = OUTPUT_DIR / "store_report.pdf"
    if report_path.exists():
        st.markdown(report_path.read_text(encoding="utf-8"))
    if pdf_path.exists():
        st.download_button(
            "Download PDF report",
            pdf_path.read_bytes(),
            file_name="store_report.pdf",
            mime="application/pdf",
        )
