# Store Manager Retail Insight Report

## Executive Snapshot
- Period analysed: 2026-08-01 to 2026-08-31.
- Revenue: Rs. 4,004,642; units sold: 5,041; invoices: 2,249.
- Average bill value: Rs. 1,781.
- Highest revenue calendar date: 2026-08-15 with Rs. 204,359.

## Question 1 Product Performance
Gross margin is revenue less product cost from product_master.csv; it is not net profit.

Top 3 products by units sold:
| Product | Units | Revenue | Gross Margin (Rs.) | Gross Margin (%) | Revenue Share (%) |
| --- | --- | --- | --- | --- | --- |
| Basic Crew T-Shirt | 576 | 227,829 | 136,821 | 60.1% | 5.7% |
| Cotton Kurti | 357 | 356,643 | 212,058 | 59.5% | 8.9% |
| Graphic Tee | 318 | 157,235 | 92,045 | 58.5% | 3.9% |

Bottom 3 products by units sold:
| Product | Units | Revenue | Gross Margin (Rs.) | Gross Margin (%) | Revenue Share (%) |
| --- | --- | --- | --- | --- | --- |
| Scarf | 11 | 5,040 | 2,785 | 55.3% | 0.1% |
| Cap | 22 | 6,578 | 4,268 | 64.9% | 0.2% |
| Anarkali Kurta Set | 25 | 36,160 | 15,535 | 43.0% | 0.9% |

Evidence notes for the slowest products:
- Scarf: 11 units, Rs. 5,040 revenue; possible reason: no SKU-level stockout evidence, so slow movement looks demand-led.
- Cap: 22 units, Rs. 6,578 revenue; possible reason: no SKU-level stockout evidence, so slow movement looks demand-led.
- Anarkali Kurta Set: 25 units, Rs. 36,160 revenue; possible reason: no SKU-level stockout evidence, so slow movement looks demand-led.

## Question 2 Size and Inventory
- Assignment size demand is calculated only for alpha apparel sizes: XS, S, M, L, and XL.
- Size M shows the strongest alpha apparel stock pressure: 924 units sold and 31 SKU-level stockout days.
- Size XS is the slowest alpha apparel size: 146 units sold and about 40.1 days of cover at the end of the period.
- Order more depth for size M in proven fast products, and order less new depth for size XS until movement improves.
- Other size systems such as footwear/kids/OneSize are excluded from the assignment size chart to avoid mixing size systems.

## Question 3 Trading Days
- Strongest weekday: Saturday with Rs. 178,132 average revenue per trading day.
- Slowest weekday: Tuesday with Rs. 86,588 average revenue per trading day.
- A small slow-day offer is worth testing, but the result should be measured against later same-weekday trading because this data does not prove promotion causality.

## Question 4 Customer Patterns
Category lift compares each segment's category share with the overall store category share. Only patterns with at least 40 support units are shown.

| Segment | Category | Segment Share % | Store Share % | Lift | Support Units | Business Meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Female - Adult (31-45) | Ethnic Wear | 24.5% | 17.1% | 1.43x | 206 | Ethnic Wear takes 1.43x its store-average share in this segment; use this as a merchandising test signal. |
| Female - Young Adult (20-30) | Accessories | 7.2% | 5.6% | 1.29x | 81 | Accessories takes 1.29x its store-average share in this segment; use this as a merchandising test signal. |
| Female - Senior (46+) | Ethnic Wear | 21.1% | 17.1% | 1.23x | 40 | Ethnic Wear takes 1.23x its store-average share in this segment; use this as a merchandising test signal. |
| Male - Teen (13-19) | Tops | 46.6% | 40.5% | 1.15x | 167 | Tops takes 1.15x its store-average share in this segment; use this as a merchandising test signal. |
| Male - Senior (46+) | Tops | 45.8% | 40.5% | 1.13x | 92 | Tops takes 1.13x its store-average share in this segment; use this as a merchandising test signal. |

- These are simulated monthly patterns and not real demographic claims.

## Question 5 Exactly 3 Actions for Next Week
1. Reorder the strongest alpha apparel size pressure point first: size M has 31 SKU-level stockout days and 924 sold units.
2. Give front-of-store space to Basic Crew T-Shirt and reduce new buying for Scarf until its sell-through improves.
3. Test a small Tuesday offer on slow-moving stock, then compare that day against the next two Tuesdays before scaling it.

## Inventory Movement Check
Expected closing = opening stock + received stock + returns + adjustments - sold units.
Returns and adjustments are included explicitly in stock movement, even when their value is zero for this monthly dataset.

| Opening Stock | Received Stock | Returns | Adjustments | Sold Units | Expected Closing | Closing Stock | Reconciliation Difference |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5,027 | 3,920 | 0 | 0 | 5,041 | 3,906 | 3,906 | 0 |

## AI Manager Explanation
**Monthly Retail Snapshot – August 2026**  
*All figures are in Indian Rupees (Rs.) unless otherwise noted.*

---

### 1. Overall Store Performance  
| Metric | Value |
|--------|-------|
| Total revenue | Rs. 4,004,641.90 |
| Total units sold | 5,041 |
| Total transactions | 2,249 |
| Average bill value | Rs. 1,780.63 |
| Highest‑revenue day | 15 Aug 2026 (Rs. 204,358.60) |

---

### 2. Top‑Selling Products  
| Product | Units | Revenue | Transactions | COGS | Gross Margin (Rs.) | Gross Margin % | Revenue Share % |
|---------|-------|---------|--------------|------|--------------------|----------------|-----------------|
| Basic Crew T‑Shirt | 576 | Rs. 227,829.0 | 516 | Rs. 91,008.0 | Rs. 136,821.0 | 60.05 % | 5.69 % |
| Cotton Kurti | 357 | Rs. 356,643.0 | 321 | Rs. 144,585.0 | Rs. 212,058.0 | 59.46 % | 8.91 % |
| Graphic Tee | 318 | Rs. 157,234.9 | 289 | Rs. 65,190.0 | Rs. 92,044.9 | 58.54 % | 3.93 % |

---

### 3. Bottom‑Performing Products  
| Product | Units | Revenue | Transactions | COGS | Gross Margin (Rs.) | Gross Margin % | Revenue Share % |
|---------|-------|---------|--------------|------|--------------------|----------------|-----------------|
| Scarf | 11 | Rs. 5,039.9 | 9 | Rs. 2,255.0 | Rs. 2,784.90 | 55.26 % | 0.13 % |
| Cap | 22 | Rs. 6,578.0 | 21 | Rs. 2,310.0 | Rs. 4,268.0 | 64.88 % | 0.16 % |
| Anarkali Kurta Set | 25 | Rs. 36,159.9 | 23 | Rs. 20,625.0 | Rs. 15,534.90 | 42.96 % | 0.90 % |

---

### 4. Alpha Size Pressure (Key Size‑Based Insights)  
| Size | Units Sold | Revenue | Stock‑out SKU Days | Ending Stock | Daily Unit Rate | Days of Cover |
|------|------------|---------|--------------------|--------------|-----------------|---------------|
| M | 924 | Rs. 675,192.8 | 31.0 | 410 | 29.81 | 13.76 |
| L | 984 | Rs. 748,265.7 | 10.0 | 380 | 31.74 | 11.97 |
| XL | 408 | Rs. 305,117.1 | 1.0 | 398 | 13.16 | 30.24 |

---

### 5. Slow‑Moving Alpha Sizes  
| Size | Units | Revenue | Stock‑out SKU Days | Ending Stock | Daily Unit Rate | Days of Cover |
|------|-------|---------|--------------------|--------------|-----------------|---------------|
| XS | 146 | Rs. 125,884.8 | 0.0 | 189 | 4.71 | 40.13 |
| XL | 408 | Rs. 305,117.1 | 1.0 | 398 | 13.16 | 30.24 |
| S | 475 | Rs. 364,431.9 | 0.0 | 380 | 15.32 | 24.80 |

*Note: Other size systems (footwear, kids, OneSize) are excluded from this analysis.*

---

### 6. Weekday Performance  
| Day | Units | Revenue | Invoices | Trading Dates | Avg. Revenue/Day |
|-----|-------|---------|----------|---------------|------------------|
| Monday | 686 | Rs. 551,747.5 | 304 | 5 | Rs. 110,349.5 |
| Tuesday | 445 | Rs. 346,354.0 | 198 | 4 | Rs. 86,588.5 |
| Wednesday | 512 | Rs. 411,548.8 | 241 | 4 | Rs. 102,887.2 |
| Thursday | 543 | Rs. 445,198.7 | 245 | 4 | Rs. 111,299.68 |
| Friday | 611 | Rs. 497,700.7 | 284 | 4 | Rs. 124,425.18 |
| Saturday | 1,147 | Rs. 890,660.2 | 488 | 5 | Rs. 178,132.04 |
| Sunday | 1,097 | Rs. 861,432.0 | 489 | 5 | Rs. 172,286.40 |

---

### 7. Customer Segment Patterns  
| Segment | Category | Segment Share % | Store Share % | Lift | Support Units | Business Insight |
|---------|----------|-----------------|---------------|------|---------------|------------------|
| Female – Adult (31‑45) | Ethnic Wear | 24.47 | 17.06 | 1.43 | 206 | Ethnic Wear is 1.43× its store‑average share in this segment. |
| Female – Young Adult (20‑30) | Accessories | 7.21 | 5.57 | 1.29 | 81 | Accessories is 1.29× its store‑average share in this segment. |
| Female – Senior (46+) | Ethnic Wear | 21.05 | 17.06 | 1.23 | 40 | Ethnic Wear is 1.23× its store‑average share in this segment. |
| Male – Teen (13‑19) | Tops | 46.65 | 40.55 | 1.15 | 167 | Tops is 1.15× its store‑average share in

## AI Usage Transparency
- Python calculated all numbers.
- AI only explained verified facts.
- Model used: openai/gpt-oss-20b via Groq OpenAI-compatible API.
- Temperature: 0.2.
- A deterministic fallback is available when the API is not configured or unavailable.
- No API key is written to report outputs.

## Limitations
- Stockout evidence is counted at SKU level and does not mean a whole size was unavailable.
- Slow products may reflect demand, display, price, or stock depth; this report gives evidence-backed possibilities, not certainty.
- Gross margin is estimated from item cost data where available and is not net profit.
- Customer lift indicates association within one simulated month, not causation or real demographic truth.
