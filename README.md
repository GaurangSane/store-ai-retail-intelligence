# Store AI

Store AI is a clean assignment project for a fashion retail store manager. It reads line-level sales data, adds product and inventory context, calculates business summaries in Python, optionally sends only verified facts to an LLM, and produces a manager-readable report.

## Business Problem

The store needs a weekly view of what is selling, which sizes are under pressure, which days need attention, what customer segments are buying, and what three actions should be taken next week. The project keeps calculations deterministic so the report can be evaluated without an API key.

## Dataset Files

- `data/sales_data.csv`: one sold item per row, required by the assignment.
- `data/product_master.csv`: SKU metadata, category, price, cost, size, and color.
- `data/inventory_daily.csv`: daily SKU-level opening stock, receipts, sales, returns, adjustments, and closing stock.

`product_master.csv` and `inventory_daily.csv` are included because sales alone cannot show stockouts, overstock, sell-through pressure, days of cover, or SKU-level inventory decisions. Sales tells what sold; inventory tells whether demand may have been capped by low stock.

## How to Run

```powershell
cd E:\Store_AI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python insight_engine.py
```

The script works without an LLM. To enable an OpenAI-compatible LLM, copy `.env.example` to `.env` locally and set `LLM_API_KEY`. Do not submit `.env`.

## Open Dashboard

```powershell
streamlit run dashboard.py
```

The dashboard has sections for Overview, Product Performance, Inventory & Sizes, Trading Days, Customer Patterns, AI Manager Actions, and Final Report.

## Monthly Workflow

1. Replace the three CSV files with the latest month of store data.
2. Run `python insight_engine.py`.
3. Review `outputs/store_report.md` or `outputs/store_report.pdf`.
4. Open `streamlit run dashboard.py` for interactive review.
5. Use the three next-week actions in the store planning meeting.

## Outputs Generated

- `outputs/store_report.md`
- `outputs/store_report.pdf`
- `outputs/ai_manager_insights.md`
- `outputs/charts/product_units.png`
- `outputs/charts/size_demand.png`
- `outputs/charts/weekday_revenue.png`

## Limitations

The project does not claim exact lost sales from stockouts. Stockout evidence is SKU-level, not proof that a full size was unavailable. Promotion recommendations are tests, not causal claims. Gross margin is not net profit. Customer patterns are simulated assignment segments and should not be generalized to real Pune shoppers.
