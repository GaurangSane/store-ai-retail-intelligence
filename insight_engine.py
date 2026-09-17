"""Clean assignment pipeline for fashion retail store insights."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from html import escape
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
DEFAULT_LLM_MODEL = "openai/gpt-oss-20b"
DEFAULT_LLM_PROVIDER = "Groq OpenAI-compatible API"
LLM_TEMPERATURE = 0.2
CUSTOMER_PATTERN_MIN_SUPPORT = 40
INVENTORY_DATE_RANGE_WARNING = (
    "Uploaded sales period does not overlap the active inventory file period. "
    "Inventory and reorder metrics may be stale unless you upload the matching inventory file."
)

REPORT_FALLBACK_EXPLANATION = (
    "Python generated this short manager interpretation from the verified store figures. "
    "The optional AI service was not used, and all business numbers still come from the CSV files."
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
REQUIRED_PRODUCT_COLUMNS = {"sku_id", "product_name", "size"}
REQUIRED_INVENTORY_COLUMNS = {
    "date",
    "sku_id",
    "opening_stock",
    "stock_received",
    "returns",
    "adjustments",
    "quantity_sold",
    "closing_stock",
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
    inventory_movement: pd.DataFrame
    weekday_perf: pd.DataFrame
    customer_patterns: pd.DataFrame
    reorder_priority: pd.DataFrame
    slow_stock_priority: pd.DataFrame
    customer_summary: list[str]
    actions: list[str]
    answers: dict


def money(value: float) -> str:
    return f"Rs. {value:,.0f}"


def prepare_sales_frame(frame: pd.DataFrame) -> pd.DataFrame:
    sales = frame.copy()
    missing = REQUIRED_SALES_COLUMNS - set(sales.columns)
    if missing:
        raise ValueError(f"sales_data.csv is missing required columns: {', '.join(sorted(missing))}")
    if sales.empty:
        raise ValueError("sales_data.csv has no sales rows")

    sales["date"] = pd.to_datetime(sales["date"], errors="raise")
    sales["quantity_sold"] = pd.to_numeric(sales["quantity_sold"], errors="raise")
    sales["total_amount (Rs.)"] = pd.to_numeric(sales["total_amount (Rs.)"], errors="raise")
    sales["sku_id"] = sales["sku_id"].astype(str).str.strip()
    sales["day_of_week"] = sales["date"].dt.day_name()
    return sales


def prepare_products_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    if frame is None:
        return None
    products = frame.copy()
    missing = REQUIRED_PRODUCT_COLUMNS - set(products.columns)
    if missing:
        raise ValueError(
            "product_master.csv is missing required columns: " + ", ".join(sorted(missing))
        )
    products["sku_id"] = products["sku_id"].astype(str).str.strip()
    if products["sku_id"].duplicated().any():
        raise ValueError("product_master.csv must contain one row per sku_id")
    if "cost_price" in products.columns:
        products["cost_price"] = pd.to_numeric(products["cost_price"], errors="coerce")
    return products


def prepare_inventory_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    if frame is None:
        return None
    inventory = frame.copy()
    missing = REQUIRED_INVENTORY_COLUMNS - set(inventory.columns)
    if missing:
        raise ValueError(
            "inventory_daily.csv is missing required columns: " + ", ".join(sorted(missing))
        )
    inventory["date"] = pd.to_datetime(inventory["date"], errors="raise")
    inventory["sku_id"] = inventory["sku_id"].astype(str).str.strip()
    for column in [
        "opening_stock",
        "stock_received",
        "returns",
        "adjustments",
        "quantity_sold",
        "closing_stock",
    ]:
        inventory[column] = pd.to_numeric(inventory[column], errors="coerce").fillna(0)
    return inventory


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    sales = prepare_sales_frame(pd.read_csv(SALES_FILE))
    products = prepare_products_frame(pd.read_csv(PRODUCT_FILE) if PRODUCT_FILE.exists() else None)
    inventory = prepare_inventory_frame(
        pd.read_csv(INVENTORY_FILE) if INVENTORY_FILE.exists() else None
    )
    return sales, products, inventory


def missing_product_skus(sales: pd.DataFrame, products: pd.DataFrame | None) -> list[str]:
    if products is None or "sku_id" not in products.columns:
        return sorted(sales["sku_id"].dropna().astype(str).unique().tolist())
    known = set(products["sku_id"].dropna().astype(str))
    return sorted(set(sales["sku_id"].dropna().astype(str)) - known)


def inventory_date_range_warning(
    sales: pd.DataFrame,
    inventory: pd.DataFrame | None,
) -> str | None:
    """Return a non-blocking warning when sales and inventory periods do not overlap."""
    if inventory is None or inventory.empty:
        return None
    sales_start, sales_end = sales["date"].min(), sales["date"].max()
    inventory_start, inventory_end = inventory["date"].min(), inventory["date"].max()
    periods_overlap = sales_start <= inventory_end and inventory_start <= sales_end
    return None if periods_overlap else INVENTORY_DATE_RANGE_WARNING


def calculate_product_performance(sales: pd.DataFrame, products: pd.DataFrame | None) -> pd.DataFrame:
    grouped = sales.groupby("product_name", as_index=False).agg(
        units=("quantity_sold", "sum"),
        revenue=("total_amount (Rs.)", "sum"),
        transactions=("sale_id", "count") if "sale_id" in sales.columns else ("sku_id", "count"),
    )
    if products is not None and {"sku_id", "cost_price"}.issubset(products.columns):
        sku_costs = products[["sku_id", "cost_price"]].drop_duplicates("sku_id").copy()
        sku_costs["cost_price"] = pd.to_numeric(sku_costs["cost_price"], errors="coerce")
        costed_sales = sales[["sku_id", "product_name", "quantity_sold"]].merge(
            sku_costs, on="sku_id", how="left", validate="many_to_one"
        )
        costed_sales["line_cogs"] = costed_sales["quantity_sold"] * costed_sales["cost_price"]
        cost_summary = costed_sales.groupby("product_name", as_index=False).agg(
            cogs=("line_cogs", lambda values: values.sum(min_count=1)),
            missing_costs=("cost_price", lambda values: int(values.isna().sum())),
        )
        grouped = grouped.merge(cost_summary, on="product_name", how="left")
        grouped["gross_margin_rs"] = grouped["revenue"] - grouped["cogs"]
        grouped.loc[grouped["missing_costs"].gt(0), "gross_margin_rs"] = float("nan")
    else:
        grouped["gross_margin_rs"] = float("nan")
    grouped["gross_margin_pct"] = grouped["gross_margin_rs"].div(grouped["revenue"]).mul(100)
    grouped["revenue_share_pct"] = grouped["revenue"] / grouped["revenue"].sum() * 100
    high_volume_cutoff = grouped["units"].quantile(0.75)
    low_volume_cutoff = grouped["units"].quantile(0.25)

    def decision(row) -> str:
        margin = row["gross_margin_pct"]
        healthy_margin = pd.notna(margin) and margin >= 35
        weak_margin = pd.isna(margin) or margin < 35
        if row["units"] >= high_volume_cutoff and healthy_margin:
            return "High volume + healthy margin: protect availability."
        if row["units"] <= low_volume_cutoff and weak_margin:
            return "Low volume + weak margin: review buying and markdown need."
        if row["units"] <= low_volume_cutoff and healthy_margin:
            return "Low volume + high margin: test display or bundling before discount."
        return "Monitor availability, margin, and sell-through together."

    grouped["manager_interpretation"] = grouped.apply(decision, axis=1)
    return grouped.sort_values(["units", "revenue"], ascending=[False, False]).reset_index(drop=True)


def calculate_inventory_movement(inventory: pd.DataFrame | None) -> pd.DataFrame:
    columns = [
        "opening_stock",
        "stock_received",
        "returns",
        "adjustments",
        "quantity_sold",
        "expected_closing",
        "closing_stock",
        "reconciliation_difference",
    ]
    if inventory is None or inventory.empty:
        return pd.DataFrame(columns=columns)

    ordered = inventory.sort_values(["sku_id", "date"])
    opening_stock = float(ordered.groupby("sku_id", sort=False)["opening_stock"].first().sum())
    closing_stock = float(ordered.groupby("sku_id", sort=False)["closing_stock"].last().sum())
    stock_received = float(ordered["stock_received"].sum())
    returns = float(ordered["returns"].sum())
    adjustments = float(ordered["adjustments"].sum())
    quantity_sold = float(ordered["quantity_sold"].sum())
    expected_closing = opening_stock + stock_received + returns + adjustments - quantity_sold
    return pd.DataFrame(
        [
            {
                "opening_stock": opening_stock,
                "stock_received": stock_received,
                "returns": returns,
                "adjustments": adjustments,
                "quantity_sold": quantity_sold,
                "expected_closing": expected_closing,
                "closing_stock": closing_stock,
                "reconciliation_difference": closing_stock - expected_closing,
            }
        ],
        columns=columns,
    )


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
    if "category" not in sales.columns:
        return pd.DataFrame(
            columns=[
                "segment",
                "category",
                "segment_share_pct",
                "store_share_pct",
                "lift",
                "support_units",
                "business_meaning",
            ]
        )

    segment_categories = sales.groupby(
        ["customer_gender", "age_group", "category"], as_index=False
    ).agg(support_units=("quantity_sold", "sum"))
    segment_totals = sales.groupby(["customer_gender", "age_group"], as_index=False).agg(
        segment_units=("quantity_sold", "sum")
    )
    store_categories = sales.groupby("category", as_index=False).agg(
        store_category_units=("quantity_sold", "sum")
    )
    store_units = float(sales["quantity_sold"].sum())

    patterns = segment_categories.merge(
        segment_totals, on=["customer_gender", "age_group"], how="left"
    ).merge(store_categories, on="category", how="left")
    patterns["segment_share_pct"] = patterns["support_units"] / patterns["segment_units"] * 100
    patterns["store_share_pct"] = patterns["store_category_units"] / store_units * 100
    patterns["lift"] = patterns["segment_share_pct"] / patterns["store_share_pct"]
    patterns["segment"] = patterns["customer_gender"] + " - " + patterns["age_group"]
    patterns["business_meaning"] = patterns.apply(
        lambda row: (
            f"{row['category']} takes {row['lift']:.2f}x its store-average share in this segment; "
            "use this as a merchandising test signal."
        ),
        axis=1,
    )
    return (
        patterns.loc[
            patterns["support_units"].ge(CUSTOMER_PATTERN_MIN_SUPPORT) & patterns["lift"].gt(1),
            [
                "segment",
                "category",
                "segment_share_pct",
                "store_share_pct",
                "lift",
                "support_units",
                "business_meaning",
            ],
        ]
        .sort_values(["lift", "support_units"], ascending=[False, False])
        .reset_index(drop=True)
    )


def customer_pattern_summaries(patterns: pd.DataFrame, limit: int = 2) -> list[str]:
    summaries = []
    for row in patterns.head(limit).itertuples(index=False):
        gender, age = row.segment.split(" - ", maxsplit=1)
        age_label = age.split(" (")[0]
        if gender == "Female" and age_label == "Young Adult":
            segment_label = "Young Adult Female"
        else:
            segment_label = f"{gender} {age_label}"
        summaries.append(f"{segment_label} segment over-indexes toward {row.category}.")
    return summaries


def customer_pattern_sentence(row) -> str:
    return (
        f"{row.segment}: {row.category} was {row.segment_share_pct:.1f}% of segment units versus "
        f"{row.store_share_pct:.1f}% store-wide ({row.lift:.2f}x lift; "
        f"{int(row.support_units)} support units)."
    )


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


def _recent_velocity(sales: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    last_date = sales["date"].max()
    first_date = max(sales["date"].min(), last_date - pd.Timedelta(days=6))
    recent_days = max((last_date - first_date).days + 1, 1)
    recent = sales.loc[sales["date"].between(first_date, last_date)]
    result = recent.groupby(group_columns, as_index=False).agg(
        recent_units=("quantity_sold", "sum")
    )
    result["recent_daily_velocity"] = result["recent_units"] / recent_days
    return result.drop(columns="recent_units")


def calculate_reorder_priority(
    sales: pd.DataFrame,
    products: pd.DataFrame | None,
    inventory: pd.DataFrame | None,
) -> pd.DataFrame:
    keys = ["product_name", "size"]
    alpha_sales = sales.loc[sales["size"].astype(str).isin(ALPHA_SIZES)].copy()
    sold = alpha_sales.groupby(keys, as_index=False).agg(units_sold=("quantity_sold", "sum"))
    velocity = _recent_velocity(alpha_sales, keys)
    result = sold.merge(velocity, on=keys, how="outer")

    if inventory is not None and products is not None:
        sku_map = products[["sku_id", "product_name", "size"]].drop_duplicates("sku_id")
        inv = inventory.merge(sku_map, on="sku_id", how="inner", validate="many_to_one")
        inv = inv.loc[inv["size"].astype(str).isin(ALPHA_SIZES)]
        stockouts = (
            inv.loc[inv["closing_stock"] <= 0]
            .groupby(keys)
            .size()
            .rename("stockout_sku_days")
            .reset_index()
        )
        ending = (
            inv.loc[inv["date"] == inv["date"].max()]
            .groupby(keys, as_index=False)
            .agg(ending_stock=("closing_stock", "sum"))
        )
        inventory_summary = ending.merge(stockouts, on=keys, how="outer")
        result = result.merge(inventory_summary, on=keys, how="outer")

    if "ending_stock" in result.columns:
        result["has_inventory_match"] = result["ending_stock"].notna()
    else:
        result["has_inventory_match"] = False
    for column in ["units_sold", "stockout_sku_days", "ending_stock", "recent_daily_velocity"]:
        if column not in result.columns:
            result[column] = 0.0
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)
    result["days_of_cover"] = result["ending_stock"].div(
        result["recent_daily_velocity"].replace(0, float("nan"))
    )
    result.loc[~result["has_inventory_match"], "days_of_cover"] = float("nan")
    positive_velocity = result.loc[result["recent_daily_velocity"] > 0, "recent_daily_velocity"]
    high_velocity = positive_velocity.quantile(0.75) if not positive_velocity.empty else float("inf")
    high = (
        result["has_inventory_match"]
        & result["stockout_sku_days"].gt(0)
        & result["days_of_cover"].lt(14)
    )
    medium = (
        result["has_inventory_match"]
        & (
            result["days_of_cover"].lt(21)
            | result["recent_daily_velocity"].ge(high_velocity)
        )
    ) & ~high
    result["reorder_priority"] = "Low"
    result.loc[medium, "reorder_priority"] = "Medium"
    result.loc[high, "reorder_priority"] = "High"
    priority_order = pd.CategoricalDtype(["High", "Medium", "Low"], ordered=True)
    result["reorder_priority"] = result["reorder_priority"].astype(priority_order)
    result = result.sort_values(
        ["reorder_priority", "stockout_sku_days", "recent_daily_velocity"],
        ascending=[True, False, False],
    ).reset_index(drop=True)
    result["reorder_priority"] = result["reorder_priority"].astype(str)
    return result[
        [
            "product_name",
            "size",
            "units_sold",
            "stockout_sku_days",
            "ending_stock",
            "recent_daily_velocity",
            "days_of_cover",
            "reorder_priority",
        ]
    ]


def calculate_slow_stock_priority(
    product_perf: pd.DataFrame,
    sales: pd.DataFrame,
    products: pd.DataFrame | None,
    inventory: pd.DataFrame | None,
) -> pd.DataFrame:
    result = product_perf[
        ["product_name", "units", "revenue", "gross_margin_pct"]
    ].rename(columns={"units": "units_sold"})
    velocity = _recent_velocity(sales, ["product_name"])
    result = result.merge(velocity, on="product_name", how="left")
    if inventory is not None and products is not None:
        inv = inventory.merge(
            products[["sku_id", "product_name"]].drop_duplicates("sku_id"),
            on="sku_id",
            how="inner",
            validate="many_to_one",
        )
        ending = (
            inv.loc[inv["date"] == inv["date"].max()]
            .groupby("product_name", as_index=False)
            .agg(ending_stock=("closing_stock", "sum"))
        )
        result = result.merge(ending, on="product_name", how="left")
    result["recent_daily_velocity"] = result["recent_daily_velocity"].fillna(0)
    if "ending_stock" not in result.columns:
        result["ending_stock"] = 0.0
    result["ending_stock"] = result["ending_stock"].fillna(0)
    result["days_of_cover"] = result["ending_stock"].div(
        result["recent_daily_velocity"].replace(0, float("nan"))
    )
    low_units = result["units_sold"].quantile(0.35)
    median_units = result["units_sold"].median()
    high = (
        result["units_sold"].le(low_units)
        & result["ending_stock"].ge(8)
        & (result["days_of_cover"].ge(45) | result["recent_daily_velocity"].eq(0))
    )
    medium = (
        result["ending_stock"].ge(5)
        & (result["units_sold"].le(median_units) | result["days_of_cover"].ge(30))
        & ~high
    )
    result["markdown_priority"] = "Low"
    result.loc[medium, "markdown_priority"] = "Medium"
    result.loc[high, "markdown_priority"] = "High"
    priority_order = pd.CategoricalDtype(["High", "Medium", "Low"], ordered=True)
    result["markdown_priority"] = result["markdown_priority"].astype(priority_order)
    result = result.sort_values(
        ["markdown_priority", "units_sold", "days_of_cover"],
        ascending=[True, True, False],
        na_position="last",
    ).reset_index(drop=True)
    result["markdown_priority"] = result["markdown_priority"].astype(str)
    return result[
        [
            "product_name",
            "units_sold",
            "revenue",
            "gross_margin_pct",
            "ending_stock",
            "days_of_cover",
            "markdown_priority",
        ]
    ]


def build_actions(
    reorder_priority: pd.DataFrame,
    slow_stock_priority: pd.DataFrame,
) -> list[str]:
    pressure_pool = reorder_priority.loc[reorder_priority["reorder_priority"] == "High"]
    if pressure_pool.empty:
        pressure_pool = reorder_priority.loc[
            reorder_priority["reorder_priority"] == "Medium"
        ]
    if pressure_pool.empty:
        pressure_pool = reorder_priority.loc[reorder_priority["units_sold"] > 0]
    pressure = (pressure_pool if not pressure_pool.empty else reorder_priority).iloc[0]
    slow_pool = slow_stock_priority.loc[slow_stock_priority["markdown_priority"] == "High"]
    if slow_pool.empty:
        slow_pool = slow_stock_priority.sort_values(["units_sold", "days_of_cover"])
    slow_names = ", ".join(slow_pool.head(3)["product_name"].tolist())
    cover_text = (
        f"{pressure['days_of_cover']:.1f} days of cover"
        if pd.notna(pressure["days_of_cover"])
        else "no recent sales cover estimate"
    )
    if pd.notna(pressure["days_of_cover"]):
        reorder_action = (
            f"Replenish {pressure['product_name']} size {pressure['size']} first: it has "
            f"{int(pressure['stockout_sku_days'])} stockout SKU-days and {cover_text}."
        )
    else:
        reorder_action = (
            f"Confirm the inventory mapping for {pressure['product_name']} size {pressure['size']} "
            f"before reordering; {int(pressure['units_sold'])} units sold but stock cover is unavailable."
        )
    return [
        reorder_action,
        f"Review {slow_names} display, price, and next buy because low unit movement appears alongside stock remaining; test presentation before markdown.",
        "Test a small Tuesday offer on slow-moving stock with margin tracking and compare against the next two Tuesdays before scaling.",
    ]


def analyze() -> Analysis:
    """Run the original CLI/default-file workflow."""
    return _analyze_prepared(*load_inputs())


def analyze_from_frames(
    sales_df: pd.DataFrame | None = None,
    products_df: pd.DataFrame | None = None,
    inventory_df: pd.DataFrame | None = None,
) -> Analysis:
    """Analyze uploaded frames, using bundled reference files for omitted inputs."""
    sales = prepare_sales_frame(
        sales_df if sales_df is not None else pd.read_csv(SALES_FILE)
    )
    products = prepare_products_frame(
        products_df
        if products_df is not None
        else (pd.read_csv(PRODUCT_FILE) if PRODUCT_FILE.exists() else None)
    )
    inventory = prepare_inventory_frame(
        inventory_df
        if inventory_df is not None
        else (pd.read_csv(INVENTORY_FILE) if INVENTORY_FILE.exists() else None)
    )
    return _analyze_prepared(sales, products, inventory)


def _analyze_prepared(
    sales: pd.DataFrame,
    products: pd.DataFrame | None,
    inventory: pd.DataFrame | None,
) -> Analysis:
    product_perf = calculate_product_performance(sales, products)
    size_perf = calculate_size_performance(sales)
    all_size_inventory = calculate_size_inventory(inventory, products, sales)
    size_inventory = alpha_size_inventory(all_size_inventory)
    inventory_movement = calculate_inventory_movement(inventory)
    weekday_perf = calculate_weekday_performance(sales)
    customer_patterns = calculate_customer_patterns(sales)
    reorder_priority = calculate_reorder_priority(sales, products, inventory)
    slow_stock_priority = calculate_slow_stock_priority(
        product_perf, sales, products, inventory
    )
    customer_summary = customer_pattern_summaries(customer_patterns)
    date_range_warning = inventory_date_range_warning(sales, inventory)

    date_revenue = sales.groupby("date")["total_amount (Rs.)"].sum().sort_values(ascending=False)
    kpis = {
        "total_revenue": float(sales["total_amount (Rs.)"].sum()),
        "total_units": int(sales["quantity_sold"].sum()),
        "transactions": int(sales["invoice_id"].nunique()) if "invoice_id" in sales.columns else int(len(sales)),
        "date_start": sales["date"].min().date().isoformat(),
        "date_end": sales["date"].max().date().isoformat(),
        "highest_revenue_date": date_revenue.index[0].date().isoformat(),
        "highest_revenue_date_sales": float(date_revenue.iloc[0]),
        "inventory_date_warning": date_range_warning,
    }
    kpis["average_bill_value"] = kpis["total_revenue"] / max(kpis["transactions"], 1)

    actions = build_actions(reorder_priority, slow_stock_priority)
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
    return Analysis(
        sales=sales,
        products=products,
        inventory=inventory,
        kpis=kpis,
        product_perf=product_perf,
        size_perf=size_perf,
        size_inventory=size_inventory,
        all_size_inventory=all_size_inventory,
        inventory_movement=inventory_movement,
        weekday_perf=weekday_perf,
        customer_patterns=customer_patterns,
        reorder_priority=reorder_priority,
        slow_stock_priority=slow_stock_priority,
        customer_summary=customer_summary,
        actions=actions,
        answers=answers,
    )


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
        "inventory_movement": analysis.inventory_movement.to_dict(orient="records"),
        "reorder_priority": analysis.reorder_priority.head(5).to_dict(orient="records"),
        "slow_stock_priority": analysis.slow_stock_priority.head(5).to_dict(orient="records"),
        "guardrails": [
            "Do not invent numbers.",
            "Do not claim exact lost sales from stockouts.",
            "Do not claim promotion causality.",
            "Do not call gross margin net profit.",
            "Do not generalize simulated customer patterns to real Pune shoppers.",
        ],
    }


def sanitize_llm_text(text: str) -> str:
    clean_lines = []
    for line in text.replace("$", "Rs. ").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("|"):
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("# ")
        if stripped[:2] in {"- ", "* "}:
            stripped = stripped[2:]
        if len(stripped) > 3 and stripped[0].isdigit() and stripped[1:3] == ". ":
            continue
        clean_lines.append(stripped)
    words = " ".join(clean_lines).split()
    return " ".join(words[:180])


def get_ai_runtime_info() -> dict:
    load_dotenv(PROJECT_ROOT / ".env")
    api_url = os.getenv("LLM_API_URL", "")
    configured_provider = os.getenv("LLM_PROVIDER", "")
    if "groq.com" in api_url.lower():
        provider = DEFAULT_LLM_PROVIDER
    elif configured_provider:
        provider = configured_provider.replace("_", " ").strip()
    else:
        provider = DEFAULT_LLM_PROVIDER
    return {
        "provider": provider,
        "model": os.getenv("LLM_MODEL") or DEFAULT_LLM_MODEL,
        "api_url": api_url,
        "temperature": LLM_TEMPERATURE,
    }


def call_llm_if_configured(facts: dict, ai_runtime: dict) -> str | None:
    api_key = os.getenv("LLM_API_KEY")
    if not ai_runtime["api_url"] or not api_key or api_key == "your_api_key_here":
        return None

    prompt = (
        "Write one short manager interpretation of these verified fashion retail facts. "
        "This is an Indian fashion retail store. Use Rs. for currency, never dollars. "
        "Use only the numbers provided. Maximum 180 words. Use short prose paragraphs only. "
        "Do not use markdown tables, headings, bullets, or numbered lists. Do not repeat the "
        "full fact package. Do not add recommendations or an action list because Python "
        "supplies exactly three approved actions separately.\n\n"
        + json.dumps(facts, default=str)
    )
    response = requests.post(
        ai_runtime["api_url"],
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": ai_runtime["model"],
            "messages": [
                {"role": "system", "content": "You explain verified retail analytics without inventing facts."},
                {"role": "user", "content": prompt},
            ],
            "temperature": ai_runtime["temperature"],
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    cleaned = sanitize_llm_text(payload["choices"][0]["message"]["content"].strip())
    return cleaned or None


def deterministic_manager_explanation(analysis: Analysis) -> str:
    top = analysis.product_perf.iloc[0]
    slow = analysis.slow_stock_priority.iloc[0]
    pressure = analysis.reorder_priority.iloc[0]
    strongest = analysis.weekday_perf.sort_values("avg_revenue_per_day", ascending=False).iloc[0]
    pattern_text = (
        " ".join(analysis.customer_summary)
        if analysis.customer_summary
        else "This sales file has no customer-category lift above the support threshold."
    )
    cover_text = (
        f"{pressure['days_of_cover']:.1f} days of cover"
        if pd.notna(pressure["days_of_cover"])
        else "no reliable cover estimate"
    )
    return (
        f"{top['product_name']} leads unit sales, while {slow['product_name']} needs closer "
        f"sell-through review. The clearest replenishment pressure is {pressure['product_name']} "
        f"size {pressure['size']}, with {int(pressure['stockout_sku_days'])} stockout SKU-days "
        f"and {cover_text}. {strongest['day_of_week']} has the strongest average revenue per "
        f"trading day. {pattern_text} These customer patterns are merchandising test signals, "
        "not demographic truth."
    )


def markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    view = df.loc[:, columns].copy()
    for column in view.columns:
        if column in {"revenue", "gross_margin_rs"}:
            view[column] = view[column].map(
                lambda value: "N/A" if pd.isna(value) else f"{value:,.0f}"
            )
        elif column in {"segment_share_pct", "store_share_pct", "gross_margin_pct", "revenue_share_pct"}:
            view[column] = view[column].map(
                lambda value: "N/A" if pd.isna(value) else f"{value:.1f}%"
            )
        elif column == "lift":
            view[column] = view[column].map(lambda value: f"{value:.2f}x")
        elif column in {"days_of_cover", "recent_daily_velocity"}:
            view[column] = view[column].map(
                lambda value: "N/A" if pd.isna(value) else f"{value:,.1f}"
            )
        elif pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:,.0f}")
    label_map = {
        "product_name": "Product",
        "units_sold": "Units Sold",
        "gross_margin_rs": "Gross Margin (Rs.)",
        "gross_margin_pct": "Gross Margin (%)",
        "revenue_share_pct": "Revenue Share (%)",
        "segment_share_pct": "Segment Share %",
        "store_share_pct": "Store Share %",
        "support_units": "Support Units",
        "business_meaning": "Business Meaning",
        "opening_stock": "Opening Stock",
        "stock_received": "Received Stock",
        "quantity_sold": "Sold Units",
        "expected_closing": "Expected Closing",
        "closing_stock": "Closing Stock",
        "reconciliation_difference": "Reconciliation Difference",
        "recent_daily_velocity": "Recent Daily Velocity",
        "days_of_cover": "Days of Cover",
        "reorder_priority": "Reorder Priority",
        "markdown_priority": "Markdown Priority",
        "manager_interpretation": "Manager Interpretation",
    }
    labels = [label_map.get(column, column.replace("_", " ").title()) for column in view.columns]
    lines = [
        "| " + " | ".join(labels) + " |",
        "| " + " | ".join(["---"] * len(labels)) + " |",
    ]
    for row in view.astype(str).itertuples(index=False):
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_report_markdown(analysis: Analysis, llm_text: str | None, ai_runtime: dict) -> str:
    top3 = analysis.product_perf.head(3)
    bottom3 = analysis.product_perf.sort_values(["units", "revenue"]).head(3)
    pressure = analysis.answers["size_inventory"]["pressure_size"]
    barely = analysis.answers["size_inventory"]["barely_size"]
    strongest = analysis.answers["trading_days"]["strongest"]
    slowest = analysis.answers["trading_days"]["slowest"]
    explanation = llm_text or deterministic_manager_explanation(analysis)
    action_lines = [f"{index}. {action}" for index, action in enumerate(analysis.actions, start=1)]
    product_columns = [
        "product_name",
        "units",
        "revenue",
        "gross_margin_pct",
        "manager_interpretation",
    ]
    pattern_columns = [
        "segment",
        "category",
        "segment_share_pct",
        "store_share_pct",
        "lift",
        "support_units",
    ]
    movement_columns = [
        "opening_stock",
        "stock_received",
        "returns",
        "adjustments",
        "quantity_sold",
        "expected_closing",
        "closing_stock",
        "reconciliation_difference",
    ]
    reorder_columns = [
        "product_name",
        "size",
        "units_sold",
        "stockout_sku_days",
        "ending_stock",
        "recent_daily_velocity",
        "days_of_cover",
        "reorder_priority",
    ]
    slow_columns = [
        "product_name",
        "units_sold",
        "revenue",
        "gross_margin_pct",
        "ending_stock",
        "days_of_cover",
        "markdown_priority",
    ]
    summary_lines = (
        [f"- {sentence}" for sentence in analysis.customer_summary]
        if analysis.customer_summary
        else ["- No customer-category lift met the minimum support threshold in this sales file."]
    )
    unknown_count = len(missing_product_skus(analysis.sales, analysis.products))
    partial_note = (
        f"- {unknown_count} sales SKU(s) were not present in the active product master, so margin and inventory metrics may be partial."
        if unknown_count
        else "- Sales SKUs matched the active product master."
    )
    inventory_date_note = (
        [f"- {analysis.kpis['inventory_date_warning']}"]
        if analysis.kpis.get("inventory_date_warning")
        else []
    )

    return "\n".join(
        [
            "# Store Manager Retail Insight Report",
            "",
            "## Executive Snapshot",
            f"- Period analysed: {analysis.kpis['date_start']} to {analysis.kpis['date_end']}.",
            f"- Revenue: {money(analysis.kpis['total_revenue'])}; units sold: {analysis.kpis['total_units']:,}; invoices: {analysis.kpis['transactions']:,}.",
            f"- Average bill value: {money(analysis.kpis['average_bill_value'])}.",
            f"- Highest revenue date: {analysis.kpis['highest_revenue_date']} with {money(analysis.kpis['highest_revenue_date_sales'])}.",
            partial_note,
            *inventory_date_note,
            "",
            "## Question 1 Product Performance",
            "Gross margin is revenue less product cost from product_master.csv; it is not net profit.",
            "High volume + healthy margin means protect availability. Low volume + weak margin means review buying/markdown. Low volume + high margin means test display or bundling before discount.",
            "",
            "Top 3 products by units sold:",
            markdown_table(top3, product_columns),
            "",
            "Bottom 3 products by units sold:",
            markdown_table(bottom3, product_columns),
            "",
            "## Question 2 Size and Inventory",
            "- Alpha apparel size demand covers XS, S, M, L, and XL only.",
            f"- Size {pressure['size']} has the strongest size pressure: {int(pressure['units'])} units sold and {int(pressure['stockout_sku_days'])} stockout SKU-days.",
            f"- Size {barely['size']} is the slowest alpha size: {int(barely['units'])} units sold and about {barely['days_of_cover']:.1f} days of cover.",
            f"- {OTHER_SIZE_SYSTEM_NOTE}",
            "",
            "## Question 3 Trading Days",
            f"- Strongest weekday: {strongest['day_of_week']} at {money(strongest['avg_revenue_per_day'])} average revenue per trading day.",
            f"- Slowest weekday: {slowest['day_of_week']} at {money(slowest['avg_revenue_per_day'])} average revenue per trading day.",
            "- Test a small Tuesday offer on slow-moving stock with margin tracking and compare against the next two Tuesdays before scaling; no sales increase is assumed.",
            "",
            "## Question 4 Customer Patterns",
            f"Lift compares each segment's category share with the overall store share. Patterns shown have at least {CUSTOMER_PATTERN_MIN_SUPPORT} support units.",
            "",
            markdown_table(analysis.customer_patterns.head(5), pattern_columns),
            "",
            "\n".join(summary_lines),
            "- These are merchandising test signals, not demographic truth.",
            "",
            "## Question 5 Exactly 3 Actions for Next Week",
            "\n".join(action_lines),
            "",
            "## Inventory Movement Check",
            "Expected closing = opening stock + received stock + returns + adjustments - sold units.",
            markdown_table(analysis.inventory_movement, movement_columns),
            "",
            "## Reorder Priority",
            "Recent daily velocity uses the final 7 calendar days available in the sales month.",
            markdown_table(analysis.reorder_priority.head(10), reorder_columns),
            "",
            "## Slow Stock / Markdown Priority",
            "Review display/price first; markdown only if stock remains slow.",
            markdown_table(analysis.slow_stock_priority.head(10), slow_columns),
            "",
            "## AI Usage Transparency",
            "Manager interpretation (maximum 180 words):",
            explanation,
            "",
            "- Python calculated all numbers and exactly three actions.",
            "- AI, when configured, only interpreted verified facts.",
            f"- Model metadata: {ai_runtime['model']} via {ai_runtime['provider']}; temperature {ai_runtime['temperature']}.",
            "- A deterministic fallback is used when the API is not configured or unavailable.",
            "- No API key or technical service detail is written to outputs.",
            "",
            "## Limitations",
            "- Stockout evidence is SKU-level and does not prove a whole size was unavailable or quantify lost sales.",
            "- Slow movement can reflect demand, display, price, or stock depth; priority labels are review signals.",
            "- Gross margin is estimated from available item cost data and is not net profit.",
            "- Customer lift is association within one month, not causation or demographic truth.",
            "",
        ]
    )


def write_ai_insights(analysis: Analysis, llm_text: str | None, ai_runtime: dict) -> None:
    explanation = llm_text or deterministic_manager_explanation(analysis)
    lines = [
        "# AI Manager Insights",
        "",
        "## Manager Explanation",
        explanation,
        "",
        "## Exactly 3 Actions",
    ]
    lines.extend(f"{index}. {action}" for index, action in enumerate(analysis.actions, start=1))
    lines.extend(
        [
            "",
            "## AI Usage Transparency",
            "Python calculated all numbers and the three actions.",
            f"Model metadata: {ai_runtime['model']} via {ai_runtime['provider']}.",
            "No API key or technical service detail is written to this file.",
        ]
    )
    (OUTPUT_DIR / "ai_manager_insights.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ai_run_metadata(ai_runtime: dict) -> None:
    metadata = {
        "provider": ai_runtime["provider"],
        "model": ai_runtime["model"],
        "ai_used_for": "Explaining verified Python-calculated retail facts only",
        "python_used_for": (
            "All calculations, category lift, inventory reconciliation, action selection, "
            "tables, charts, and report generation"
        ),
        "temperature": ai_runtime["temperature"],
        "fallback_available": True,
    }
    (OUTPUT_DIR / "ai_run_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )


def generate_outputs(analysis: Analysis) -> tuple[str, dict]:
    """Regenerate charts, Markdown, PDF, and AI metadata for one analysis run."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    generate_charts(analysis)
    ai_runtime = get_ai_runtime_info()
    try:
        llm_text = call_llm_if_configured(fact_package(analysis), ai_runtime)
    except Exception:
        print("WARNING: AI explanation unavailable; deterministic explanation used.")
        llm_text = None
    explanation = llm_text or deterministic_manager_explanation(analysis)
    report = build_report_markdown(analysis, explanation, ai_runtime)
    (OUTPUT_DIR / "store_report.md").write_text(report, encoding="utf-8")
    write_ai_insights(analysis, explanation, ai_runtime)
    write_ai_run_metadata(ai_runtime)
    write_pdf(report)
    return explanation, ai_runtime


def write_pdf(markdown_text: str) -> None:
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#243b53")
    styles["Heading2"].textColor = colors.HexColor("#326273")
    styles["Heading2"].spaceBefore = 8
    styles["Heading2"].spaceAfter = 5
    styles["Heading2"].keepWithNext = True
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12
    bullet_style = ParagraphStyle(
        "ReportBullet",
        parent=styles["BodyText"],
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3,
    )
    linked_number_style = ParagraphStyle(
        "LinkedReportNumber", parent=bullet_style, keepWithNext=True
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    table_cell_style = ParagraphStyle(
        "TableCell", parent=styles["BodyText"], fontSize=7, leading=8
    )
    doc = SimpleDocTemplate(
        str(OUTPUT_DIR / "store_report.pdf"),
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=14 * mm,
        title="Store Manager Retail Insight Report",
        author="Store AI",
    )

    def table_widths(headers: list[str]) -> list[float]:
        if "Business Meaning" in headers:
            weights = [1.7, 1.0, 0.9, 0.9, 0.6, 0.8, 2.5]
        elif "Manager Interpretation" in headers:
            weights = [1.6, 0.5, 0.8, 0.8, 2.7]
        elif "Reorder Priority" in headers:
            weights = [1.7, 0.5, 0.7, 0.9, 0.8, 1.0, 0.8, 0.9]
        elif "Markdown Priority" in headers:
            weights = [1.8, 0.7, 0.9, 0.9, 0.8, 0.8, 1.0]
        elif "Gross Margin (Rs.)" in headers:
            weights = [2.1, 0.7, 1.0, 1.2, 1.0, 1.0]
        else:
            weights = [1.0] * len(headers)
        scale = doc.width / sum(weights)
        return [weight * scale for weight in weights]

    def on_page(canvas, document) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d9e2ec"))
        canvas.line(document.leftMargin, 10 * mm, landscape(A4)[0] - document.rightMargin, 10 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#627d98"))
        canvas.drawRightString(
            landscape(A4)[0] - document.rightMargin,
            6.5 * mm,
            f"Store AI | Page {document.page}",
        )
        canvas.restoreState()

    story = []
    lines = markdown_text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 5))
        elif stripped.startswith("# "):
            story.append(Paragraph(escape(stripped[2:]), styles["Title"]))
            story.append(Spacer(1, 10))
        elif stripped.startswith("## "):
            story.append(Paragraph(escape(stripped[3:]), styles["Heading2"]))
        elif stripped.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            rows = [
                [cell.strip() for cell in table_line.strip("|").split("|")]
                for table_line in table_lines
            ]
            rows = [rows[0], *rows[2:]]
            pdf_rows = []
            for row_index, row in enumerate(rows):
                cell_style = table_header_style if row_index == 0 else table_cell_style
                pdf_rows.append([Paragraph(escape(cell), cell_style) for cell in row])
            table = Table(pdf_rows, colWidths=table_widths(rows[0]), repeatRows=1, hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#326273")),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#bcccdc")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 6))
            continue
        elif stripped.startswith("- "):
            story.append(Paragraph(escape(stripped[2:]), bullet_style, bulletText="-"))
        elif len(stripped) > 3 and stripped[0].isdigit() and stripped[1:3] == ". ":
            number_style = linked_number_style if stripped.startswith(("1. ", "2. ")) else bullet_style
            story.append(Paragraph(escape(stripped[3:]), number_style, bulletText=stripped[:2]))
        else:
            story.append(Paragraph(escape(stripped), styles["BodyText"]))
            story.append(Spacer(1, 3))
        index += 1
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


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
    analysis = analyze()
    generate_outputs(analysis)
    print_terminal_answers(analysis)
    print("\nGenerated outputs/store_report.md")
    print("Generated outputs/store_report.pdf")
    print("Generated outputs/ai_manager_insights.md")
    print("Generated outputs/ai_run_metadata.json")
    print("Generated outputs/charts/product_units.png")
    print("Generated outputs/charts/size_demand.png")
    print("Generated outputs/charts/weekday_revenue.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
