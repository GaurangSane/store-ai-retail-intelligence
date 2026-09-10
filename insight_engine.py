"""Clean assignment pipeline for fashion retail store insights."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CHART_DIR = OUTPUT_DIR / "charts"
DOCS_DIR = PROJECT_ROOT / "docs"

SALES_FILE = DATA_DIR / "sales_data.csv"
PRODUCT_FILE = DATA_DIR / "product_master.csv"
INVENTORY_FILE = DATA_DIR / "inventory_daily.csv"
ALPHA_SIZES = ["XS", "S", "M", "L", "XL"]
OTHER_SIZE_SYSTEM_NOTE = (
    "Other size systems such as footwear/kids/OneSize are excluded from the assignment "
    "size chart to avoid mixing size systems."
)

REPORT_FALLBACK_EXPLANATION = (
    "This explanation was generated from deterministic Python-calculated facts. "
    "The LLM layer is optional; all business numbers in this report come from the CSV files."
)

AI_INSIGHTS_FALLBACK_EXPLANATION = (
    "LLM was not used for this run. Deterministic manager explanations were generated from "
    "verified Python calculations."
)

REQUIRED_SALES_COLUMNS = {
    "date",
    "product_name",
    "size",
    "quantity_sold",
    "total_amount (Rs.)",
    "customer_gender",
    "age_group",
    "sku_id",
}


@dataclass
class Analysis:
    sales: pd.DataFrame
    products: pd.DataFrame | None
    inventory: pd.DataFrame | None
    kpis: dict
    product_perf: pd.DataFrame
    size_perf: pd.DataFrame
    size_inventory: pd.DataFrame
    all_size_inventory: pd.DataFrame
    weekday_perf: pd.DataFrame
    customer_patterns: pd.DataFrame
    actions: list[str]
    answers: dict


def money(value: float) -> str:
    return f"Rs. {value:,.0f}"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    sales = pd.read_csv(SALES_FILE)
    missing = REQUIRED_SALES_COLUMNS - set(sales.columns)
    if missing:
        raise ValueError(f"sales_data.csv is missing required columns: {', '.join(sorted(missing))}")

    sales["date"] = pd.to_datetime(sales["date"], errors="raise")
    sales["quantity_sold"] = pd.to_numeric(sales["quantity_sold"], errors="raise")
    sales["total_amount (Rs.)"] = pd.to_numeric(sales["total_amount (Rs.)"], errors="raise")

    products = pd.read_csv(PRODUCT_FILE) if PRODUCT_FILE.exists() else None
    inventory = pd.read_csv(INVENTORY_FILE) if INVENTORY_FILE.exists() else None
    if inventory is not None:
        inventory["date"] = pd.to_datetime(inventory["date"], errors="raise")
        for column in ["opening_stock", "stock_received", "quantity_sold", "closing_stock"]:
            inventory[column] = pd.to_numeric(inventory[column], errors="coerce").fillna(0)
    return sales, products, inventory


def calculate_product_performance(sales: pd.DataFrame, products: pd.DataFrame | None) -> pd.DataFrame:
    grouped = sales.groupby("product_name", as_index=False).agg(
        units=("quantity_sold", "sum"),
        revenue=("total_amount (Rs.)", "sum"),
        transactions=("sale_id", "count") if "sale_id" in sales.columns else ("sku_id", "count"),
    )
    if products is not None and {"product_name", "cost_price"}.issubset(products.columns):
        cost = products.groupby("product_name", as_index=False).agg(avg_cost=("cost_price", "mean"))
        grouped = grouped.merge(cost, on="product_name", how="left")
        grouped["gross_margin_rs"] = grouped["revenue"] - grouped["units"] * grouped["avg_cost"].fillna(0)
    else:
        grouped["gross_margin_rs"] = 0
    grouped["revenue_share_pct"] = grouped["revenue"] / grouped["revenue"].sum() * 100
    return grouped.sort_values(["units", "revenue"], ascending=[False, False]).reset_index(drop=True)


def calculate_size_performance(sales: pd.DataFrame) -> pd.DataFrame:
    alpha_sales = sales.loc[sales["size"].astype(str).isin(ALPHA_SIZES)]
    grouped = (
        alpha_sales.groupby("size", as_index=False)
        .agg(units=("quantity_sold", "sum"), revenue=("total_amount (Rs.)", "sum"), skus_sold=("sku_id", "nunique"))
    )
    ordered = pd.DataFrame({"size": ALPHA_SIZES}).merge(grouped, on="size", how="left").fillna(0)
    ordered["size"] = pd.Categorical(ordered["size"], categories=ALPHA_SIZES, ordered=True)
    return ordered.sort_values("size").reset_index(drop=True)


def calculate_size_inventory(inventory: pd.DataFrame | None, products: pd.DataFrame | None, sales: pd.DataFrame) -> pd.DataFrame:
    if inventory is None or products is None or "size" not in products.columns:
        fallback = calculate_size_performance(sales)
        fallback["stockout_sku_days"] = 0
        fallback["ending_stock"] = 0
        fallback["days_of_cover"] = 0.0
        return fallback

    inv = inventory.merge(products[["sku_id", "size", "product_name"]].drop_duplicates("sku_id"), on="sku_id", how="left")
    stockout = inv.loc[inv["closing_stock"] <= 0].groupby("size").size().rename("stockout_sku_days")
    ending_date = inv["date"].max()
    ending = inv.loc[inv["date"] == ending_date].groupby("size")["closing_stock"].sum().rename("ending_stock")
    sold = sales.groupby("size")["quantity_sold"].sum().rename("units")
    revenue = sales.groupby("size")["total_amount (Rs.)"].sum().rename("revenue")
    days = max((sales["date"].max() - sales["date"].min()).days + 1, 1)
    result = pd.concat([sold, revenue, stockout, ending], axis=1).fillna(0).reset_index()
    result["daily_unit_rate"] = result["units"] / days
    result["days_of_cover"] = result.apply(
        lambda row: row["ending_stock"] / row["daily_unit_rate"] if row["daily_unit_rate"] > 0 else 0,
        axis=1,
    )
    return result.sort_values(["units", "stockout_sku_days"], ascending=[False, False]).reset_index(drop=True)


def alpha_size_inventory(size_inventory: pd.DataFrame) -> pd.DataFrame:
    alpha = size_inventory.loc[size_inventory["size"].astype(str).isin(ALPHA_SIZES)].copy()
    ordered = pd.DataFrame({"size": ALPHA_SIZES}).merge(alpha, on="size", how="left").fillna(0)
    for column in ["units", "revenue", "stockout_sku_days", "ending_stock", "daily_unit_rate", "days_of_cover"]:
        if column not in ordered.columns:
            ordered[column] = 0
    ordered["size"] = pd.Categorical(ordered["size"], categories=ALPHA_SIZES, ordered=True)
    return ordered.sort_values("size").reset_index(drop=True)


def calculate_weekday_performance(sales: pd.DataFrame) -> pd.DataFrame:
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    grouped = sales.groupby("day_of_week", as_index=False).agg(
        units=("quantity_sold", "sum"),
        revenue=("total_amount (Rs.)", "sum"),
        invoices=("invoice_id", "nunique") if "invoice_id" in sales.columns else ("sku_id", "count"),
        trading_dates=("date", "nunique"),
    )
    grouped["avg_revenue_per_day"] = grouped["revenue"] / grouped["trading_dates"]
    grouped["day_of_week"] = pd.Categorical(grouped["day_of_week"], categories=order, ordered=True)
    return grouped.sort_values("day_of_week").reset_index(drop=True)


def calculate_customer_patterns(sales: pd.DataFrame) -> pd.DataFrame:
    pattern_column = "category" if "category" in sales.columns else "product_name"
    return (
        sales.groupby(["customer_gender", "age_group", pattern_column], as_index=False)
        .agg(units=("quantity_sold", "sum"), revenue=("total_amount (Rs.)", "sum"))
        .sort_values(["units", "revenue"], ascending=[False, False])
        .head(5)
        .reset_index(drop=True)
    )


def customer_pattern_sentence(row) -> str:
    segment = f"{row.age_group} {row.customer_gender}".replace("Young Adult (20-30)", "Young Adult").replace("Adult (31-45)", "Adult")
    if hasattr(row, "category"):
        return f"{segment} customers bought more {row.category} in this simulated month: {int(row.units)} units, {money(row.revenue)} revenue."
    return f"{segment} customers bought more {row.product_name} in this simulated month: {int(row.units)} units, {money(row.revenue)} revenue."


def stock_notes_for_product(product: str, sales: pd.DataFrame, inventory: pd.DataFrame | None) -> str:
    product_sales = sales.loc[sales["product_name"] == product]
    if inventory is None or product_sales.empty:
        return "low observed demand in sales rows"
    sku_ids = set(product_sales["sku_id"].dropna())
    inv = inventory.loc[inventory["sku_id"].isin(sku_ids)]
    stockout_sku_days = int((inv["closing_stock"] <= 0).sum())
    if stockout_sku_days:
        return f"{stockout_sku_days} SKU-level stockout days may have capped sales"
    return "no SKU-level stockout evidence, so slow movement looks demand-led"


def build_actions(product_perf: pd.DataFrame, size_inventory: pd.DataFrame, weekday_perf: pd.DataFrame) -> list[str]:
    top_product = product_perf.iloc[0]["product_name"]
    slow_product = product_perf.sort_values(["units", "revenue"], ascending=[True, True]).iloc[0]["product_name"]
    pressure = size_inventory.sort_values(["stockout_sku_days", "units"], ascending=[False, False]).iloc[0]
    slow_day = weekday_perf.sort_values("avg_revenue_per_day").iloc[0]["day_of_week"]
    return [
        f"Reorder the strongest alpha apparel size pressure point first: size {pressure['size']} has {int(pressure['stockout_sku_days'])} SKU-level stockout days and {int(pressure['units'])} sold units.",
        f"Give front-of-store space to {top_product} and reduce new buying for {slow_product} until its sell-through improves.",
        f"Test a small {slow_day} offer on slow-moving stock, then compare that day against the next two {slow_day}s before scaling it.",
    ]


def analyze() -> Analysis:
    sales, products, inventory = load_inputs()
    product_perf = calculate_product_performance(sales, products)
    size_perf = calculate_size_performance(sales)
    all_size_inventory = calculate_size_inventory(inventory, products, sales)
    size_inventory = alpha_size_inventory(all_size_inventory)
    weekday_perf = calculate_weekday_performance(sales)
    customer_patterns = calculate_customer_patterns(sales)

    date_revenue = sales.groupby("date")["total_amount (Rs.)"].sum().sort_values(ascending=False)
    kpis = {
        "total_revenue": float(sales["total_amount (Rs.)"].sum()),
        "total_units": int(sales["quantity_sold"].sum()),
        "transactions": int(sales["invoice_id"].nunique()) if "invoice_id" in sales.columns else int(len(sales)),
        "date_start": sales["date"].min().date().isoformat(),
        "date_end": sales["date"].max().date().isoformat(),
        "highest_revenue_date": date_revenue.index[0].date().isoformat(),
        "highest_revenue_date_sales": float(date_revenue.iloc[0]),
    }
    kpis["average_bill_value"] = kpis["total_revenue"] / max(kpis["transactions"], 1)

    actions = build_actions(product_perf, size_inventory, weekday_perf)
    top3 = product_perf.head(3)
    bottom3 = product_perf.sort_values(["units", "revenue"], ascending=[True, True]).head(3)
    strongest_day = weekday_perf.sort_values("avg_revenue_per_day", ascending=False).iloc[0]
    slowest_day = weekday_perf.sort_values("avg_revenue_per_day").iloc[0]
    pressure_size = size_inventory.sort_values(["stockout_sku_days", "units"], ascending=[False, False]).iloc[0]
    barely_size = size_inventory.sort_values(["units", "days_of_cover"], ascending=[True, False]).iloc[0]

    answers = {
        "product_performance": {
            "top3": top3,
            "bottom3": bottom3,
            "text": (
                f"The best sellers are {', '.join(top3['product_name'].tolist())}. "
                f"The slowest products are {', '.join(bottom3['product_name'].tolist())}; "
                "their reasons should be read as evidence, not certainty."
            ),
        },
        "size_inventory": {
            "pressure_size": pressure_size,
            "barely_size": barely_size,
            "text": (
                f"Among alpha apparel sizes, size {pressure_size['size']} has the strongest pressure with "
                f"{int(pressure_size['stockout_sku_days'])} SKU-level stockout days and "
                f"{int(pressure_size['units'])} sold units. Size {barely_size['size']} is the slowest alpha size "
                f"with {int(barely_size['units'])} units sold. {OTHER_SIZE_SYSTEM_NOTE}"
            ),
        },
        "trading_days": {
            "strongest": strongest_day,
            "slowest": slowest_day,
            "text": (
                f"{strongest_day['day_of_week']} is strongest at "
                f"{money(strongest_day['avg_revenue_per_day'])} average revenue per trading day. "
                f"{slowest_day['day_of_week']} is slowest at {money(slowest_day['avg_revenue_per_day'])}; "
                "a limited offer can be tested, but the data does not prove promotion causality."
            ),
        },
        "customer_patterns": customer_patterns.head(2),
        "actions": actions,
    }
    return Analysis(sales, products, inventory, kpis, product_perf, size_perf, size_inventory, all_size_inventory, weekday_perf, customer_patterns, actions, answers)


def generate_charts(analysis: Analysis) -> None:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(9, 5))
    top_products = analysis.product_perf.head(10).sort_values("units")
    plt.barh(top_products["product_name"], top_products["units"], color="#326273")
    plt.xlabel("Units sold")
    plt.title("Top Products by Units Sold")
    plt.tight_layout()
    plt.savefig(CHART_DIR / "product_units.png", dpi=160)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.bar(analysis.size_perf["size"].astype(str), analysis.size_perf["units"], color="#7a4e2d")
    plt.xlabel("Size")
    plt.ylabel("Units sold")
    plt.title("Alpha Apparel Size Demand")
    plt.tight_layout()
    plt.savefig(CHART_DIR / "size_demand.png", dpi=160)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.bar(analysis.weekday_perf["day_of_week"].astype(str), analysis.weekday_perf["avg_revenue_per_day"], color="#5b6c5d")
    plt.xlabel("Weekday")
    plt.ylabel("Average revenue per trading day (Rs.)")
    plt.title("Weekday Revenue Strength")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(CHART_DIR / "weekday_revenue.png", dpi=160)
    plt.close()


def fact_package(analysis: Analysis) -> dict:
    return {
        "kpis": analysis.kpis,
        "top_products": analysis.product_perf.head(3).to_dict(orient="records"),
        "bottom_products": analysis.product_perf.sort_values(["units", "revenue"], ascending=[True, True]).head(3).to_dict(orient="records"),
        "alpha_size_pressure": analysis.size_inventory.sort_values(["stockout_sku_days", "units"], ascending=[False, False]).head(3).to_dict(orient="records"),
        "slow_alpha_sizes": analysis.size_inventory.sort_values(["units", "days_of_cover"], ascending=[True, False]).head(3).to_dict(orient="records"),
        "other_size_system_note": OTHER_SIZE_SYSTEM_NOTE,
        "weekday_performance": analysis.weekday_perf.to_dict(orient="records"),
        "customer_patterns": analysis.customer_patterns.head(5).to_dict(orient="records"),
        "actions": analysis.actions,
        "guardrails": [
            "Do not invent numbers.",
            "Do not claim exact lost sales from stockouts.",
            "Do not claim promotion causality.",
            "Do not call gross margin net profit.",
            "Do not generalize simulated customer patterns to real Pune shoppers.",
        ],
    }


def sanitize_llm_text(text: str) -> str:
    return text.replace("$", "Rs. ")


def call_llm_if_configured(facts: dict) -> str | None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_url = os.getenv("LLM_API_URL")
    model = os.getenv("LLM_MODEL")
    api_key = os.getenv("LLM_API_KEY")
    if not api_url or not model or not api_key or api_key == "your_api_key_here":
        return None

    prompt = (
        "Explain these verified fashion retail facts for a store manager. "
        "This is an Indian fashion retail store. Use Rs. for currency, never dollars. "
        "Use only the numbers provided. Keep the answer practical and include exactly three actions.\n\n"
        + json.dumps(facts, default=str)
    )
    response = requests.post(
        api_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You explain verified retail analytics without inventing facts."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    return sanitize_llm_text(payload["choices"][0]["message"]["content"].strip())


def markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    view = df.loc[:, columns].copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:,.0f}")
    labels = [column.replace("_", " ").title() for column in view.columns]
    lines = [
        "| " + " | ".join(labels) + " |",
        "| " + " | ".join(["---"] * len(labels)) + " |",
    ]
    for row in view.astype(str).itertuples(index=False):
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_report_markdown(analysis: Analysis, llm_text: str | None) -> str:
    top3 = analysis.product_perf.head(3)
    bottom3 = analysis.product_perf.sort_values(["units", "revenue"], ascending=[True, True]).head(3)
    pressure = analysis.answers["size_inventory"]["pressure_size"]
    barely = analysis.answers["size_inventory"]["barely_size"]
    strongest = analysis.answers["trading_days"]["strongest"]
    slowest = analysis.answers["trading_days"]["slowest"]

    bottom_lines = []
    for row in bottom3.itertuples(index=False):
        bottom_lines.append(f"- {row.product_name}: {int(row.units)} units, {money(row.revenue)} revenue; possible reason: {stock_notes_for_product(row.product_name, analysis.sales, analysis.inventory)}.")

    customer_lines = []
    for row in analysis.customer_patterns.head(2).itertuples(index=False):
        customer_lines.append(f"- {customer_pattern_sentence(row)}")

    action_lines = [f"{index}. {action}" for index, action in enumerate(analysis.actions, start=1)]

    return "\n".join(
        [
            "# Store Manager Retail Insight Report",
            "",
            "## Executive Snapshot",
            f"- Period analysed: {analysis.kpis['date_start']} to {analysis.kpis['date_end']}.",
            f"- Revenue: {money(analysis.kpis['total_revenue'])}; units sold: {analysis.kpis['total_units']:,}; invoices: {analysis.kpis['transactions']:,}.",
            f"- Average bill value: {money(analysis.kpis['average_bill_value'])}.",
            f"- Highest revenue calendar date: {analysis.kpis['highest_revenue_date']} with {money(analysis.kpis['highest_revenue_date_sales'])}.",
            "",
            "## Question 1: Product Performance",
            "Top 3 products by units sold:",
            markdown_table(top3, ["product_name", "units", "revenue", "revenue_share_pct"]),
            "",
            "Bottom 3 products by units sold:",
            "\n".join(bottom_lines),
            "",
            "## Question 2: Size and Inventory",
            "- Assignment size demand is calculated only for alpha apparel sizes: XS, S, M, L, and XL.",
            f"- Size {pressure['size']} shows the strongest alpha apparel stock pressure: {int(pressure['units'])} units sold and {int(pressure['stockout_sku_days'])} SKU-level stockout days.",
            f"- Size {barely['size']} is the slowest alpha apparel size: {int(barely['units'])} units sold and about {barely['days_of_cover']:.1f} days of cover at the end of the period.",
            f"- Order more depth for size {pressure['size']} in proven fast products, and order less new depth for size {barely['size']} until movement improves.",
            f"- {OTHER_SIZE_SYSTEM_NOTE}",
            "",
            "## Question 3: Trading Days",
            f"- Strongest weekday: {strongest['day_of_week']} with {money(strongest['avg_revenue_per_day'])} average revenue per trading day.",
            f"- Slowest weekday: {slowest['day_of_week']} with {money(slowest['avg_revenue_per_day'])} average revenue per trading day.",
            "- A small slow-day offer is worth testing, but the result should be measured against later same-weekday trading because this data does not prove promotion causality.",
            "",
            "## Question 4: Customer Patterns",
            "\n".join(customer_lines),
            "- These are simulated assignment patterns and should not be generalized to real Pune shoppers.",
            "",
            "## Question 5: Exactly 3 Actions for Next Week",
            "\n".join(action_lines),
            "",
            "## AI Manager Explanation",
            llm_text if llm_text else REPORT_FALLBACK_EXPLANATION,
            "",
            "## Limitations",
            "- Stockout evidence is counted at SKU level and does not mean a whole size was unavailable.",
            "- Slow products may reflect demand, display, price, or stock depth; this report gives evidence-backed possibilities, not certainty.",
            "- Gross margin is estimated from item cost data where available and is not net profit.",
            "- The dataset is assignment data, so customer patterns are useful for practice decisions but not demographic truth.",
            "",
        ]
    )


def write_ai_insights(analysis: Analysis, llm_text: str | None) -> None:
    facts = fact_package(analysis)
    lines = [
        "# AI Manager Insights",
        "",
        "Python calculated the facts below. The LLM, if configured, only explains these verified facts.",
        "",
        "## Verified Facts Sent to LLM",
        f"- Revenue: {money(facts['kpis']['total_revenue'])}",
        f"- Units sold: {facts['kpis']['total_units']:,}",
        f"- Top products: {', '.join(row['product_name'] for row in facts['top_products'])}",
        f"- Bottom products: {', '.join(row['product_name'] for row in facts['bottom_products'])}",
        "",
        "## Manager Explanation",
        llm_text or AI_INSIGHTS_FALLBACK_EXPLANATION,
        "",
        "## Exactly 3 Actions",
    ]
    lines.extend(f"{index}. {action}" for index, action in enumerate(analysis.actions, start=1))
    (OUTPUT_DIR / "ai_manager_insights.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_pdf(markdown_text: str) -> None:
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#243b53")
    styles["Heading2"].textColor = colors.HexColor("#326273")
    doc = SimpleDocTemplate(str(OUTPUT_DIR / "store_report.pdf"), pagesize=A4, rightMargin=40, leftMargin=40, topMargin=42, bottomMargin=36)
    story = []
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 8))
        elif stripped.startswith("# "):
            story.append(Paragraph(stripped[2:], styles["Title"]))
            story.append(Spacer(1, 10))
        elif stripped.startswith("## "):
            story.append(Paragraph(stripped[3:], styles["Heading2"]))
            story.append(Spacer(1, 6))
        elif stripped.startswith("|"):
            story.append(Paragraph(stripped.replace("|", " | "), styles["Code"]))
        else:
            story.append(Paragraph("<br/>".join(wrap(stripped, 100)), styles["BodyText"]))
            story.append(Spacer(1, 4))
    doc.build(story)


def print_terminal_answers(analysis: Analysis) -> None:
    print("\nSTORE MANAGER ANSWERS")
    print("1. Products")
    print(analysis.answers["product_performance"]["text"])
    for row in analysis.answers["product_performance"]["bottom3"].itertuples(index=False):
        print(f"   Slow: {row.product_name} - {int(row.units)} units; {stock_notes_for_product(row.product_name, analysis.sales, analysis.inventory)}.")
    print("\n2. Sizes")
    print(analysis.answers["size_inventory"]["text"])
    print("\n3. Trading days")
    print(analysis.answers["trading_days"]["text"])
    print("\n4. Customer patterns")
    for row in analysis.customer_patterns.head(2).itertuples(index=False):
        print(f"   {customer_pattern_sentence(row)}")
    print("\n5. Exactly 3 actions for next week")
    for index, action in enumerate(analysis.actions, start=1):
        print(f"   {index}. {action}")


def main() -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    analysis = analyze()
    generate_charts(analysis)
    facts = fact_package(analysis)
    try:
        llm_text = call_llm_if_configured(facts)
    except Exception as exc:
        print(f"WARNING: LLM request failed; deterministic explanations were used. Technical detail: {exc}")
        llm_text = None
    report = build_report_markdown(analysis, llm_text)
    (OUTPUT_DIR / "store_report.md").write_text(report, encoding="utf-8")
    write_ai_insights(analysis, llm_text)
    write_pdf(report)
    print_terminal_answers(analysis)
    print("\nGenerated outputs/store_report.md")
    print("Generated outputs/store_report.pdf")
    print("Generated outputs/ai_manager_insights.md")
    print("Generated outputs/charts/product_units.png")
    print("Generated outputs/charts/size_demand.png")
    print("Generated outputs/charts/weekday_revenue.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
