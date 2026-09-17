# Store Manager Retail Insight Report

## Executive Snapshot
- Period analysed: 2026-08-01 to 2026-08-31.
- Revenue: Rs. 4,004,642; units sold: 5,041; invoices: 2,249.
- Average bill value: Rs. 1,781.
- Highest revenue date: 2026-08-15 with Rs. 204,359.
- Sales SKUs matched the active product master.

## Question 1 Product Performance
Gross margin is revenue less product cost from product_master.csv; it is not net profit.
High volume + healthy margin means protect availability. Low volume + weak margin means review buying/markdown. Low volume + high margin means test display or bundling before discount.

Top 3 products by units sold:
| Product | Units | Revenue | Gross Margin (%) | Manager Interpretation |
| --- | --- | --- | --- | --- |
| Basic Crew T-Shirt | 576 | 227,829 | 60.1% | High volume + healthy margin: protect availability. |
| Cotton Kurti | 357 | 356,643 | 59.5% | High volume + healthy margin: protect availability. |
| Graphic Tee | 318 | 157,235 | 58.5% | High volume + healthy margin: protect availability. |

Bottom 3 products by units sold:
| Product | Units | Revenue | Gross Margin (%) | Manager Interpretation |
| --- | --- | --- | --- | --- |
| Scarf | 11 | 5,040 | 55.3% | Low volume + high margin: test display or bundling before discount. |
| Cap | 22 | 6,578 | 64.9% | Low volume + high margin: test display or bundling before discount. |
| Anarkali Kurta Set | 25 | 36,160 | 43.0% | Low volume + high margin: test display or bundling before discount. |

## Question 2 Size and Inventory
- Alpha apparel size demand covers XS, S, M, L, and XL only.
- Size M has the strongest size pressure: 924 units sold and 31 stockout SKU-days.
- Size XS is the slowest alpha size: 146 units sold and about 40.1 days of cover.
- Other size systems such as footwear/kids/OneSize are excluded from the assignment size chart to avoid mixing size systems.

## Question 3 Trading Days
- Strongest weekday: Saturday at Rs. 178,132 average revenue per trading day.
- Slowest weekday: Tuesday at Rs. 86,588 average revenue per trading day.
- Test a small Tuesday offer on slow-moving stock with margin tracking and compare against the next two Tuesdays before scaling; no sales increase is assumed.

## Question 4 Customer Patterns
Lift compares each segment's category share with the overall store share. Patterns shown have at least 40 support units.

| Segment | Category | Segment Share % | Store Share % | Lift | Support Units |
| --- | --- | --- | --- | --- | --- |
| Female - Adult (31-45) | Ethnic Wear | 24.5% | 17.1% | 1.43x | 206 |
| Female - Young Adult (20-30) | Accessories | 7.2% | 5.6% | 1.29x | 81 |
| Female - Senior (46+) | Ethnic Wear | 21.1% | 17.1% | 1.23x | 40 |
| Male - Teen (13-19) | Tops | 46.6% | 40.5% | 1.15x | 167 |
| Male - Senior (46+) | Tops | 45.8% | 40.5% | 1.13x | 92 |

- Female Adult segment over-indexes toward Ethnic Wear.
- Young Adult Female segment over-indexes toward Accessories.
- These are merchandising test signals, not demographic truth.

## Question 5 Exactly 3 Actions for Next Week
1. Replenish Cotton Kurti size M first: it has 26 stockout SKU-days and 9.2 days of cover.
2. Review Scarf, Cap, Anarkali Kurta Set display, price, and next buy because low unit movement appears alongside stock remaining; test presentation before markdown.
3. Test a small Tuesday offer on slow-moving stock with margin tracking and compare against the next two Tuesdays before scaling.

## Inventory Movement Check
Expected closing = opening stock + received stock + returns + adjustments - sold units.
| Opening Stock | Received Stock | Returns | Adjustments | Sold Units | Expected Closing | Closing Stock | Reconciliation Difference |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5,027 | 3,920 | 0 | 0 | 5,041 | 3,906 | 3,906 | 0 |

## Reorder Priority
Recent daily velocity uses the final 7 calendar days available in the sales month.
| Product | Size | Units Sold | Stockout Sku Days | Ending Stock | Recent Daily Velocity | Days of Cover | Reorder Priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cotton Kurti | M | 79 | 26 | 17 | 1.9 | 9.2 | High |
| Basic Crew T-Shirt | M | 213 | 4 | 15 | 8.0 | 1.9 | High |
| Basic Crew T-Shirt | L | 177 | 3 | 15 | 7.0 | 2.1 | High |
| Printed Top | L | 74 | 3 | 25 | 2.3 | 10.9 | High |
| Polo T-Shirt | L | 71 | 1 | 33 | 2.4 | 13.6 | High |
| Denim Jeggings | M | 59 | 1 | 12 | 2.3 | 5.2 | High |
| Denim Jeggings | L | 65 | 1 | 14 | 2.0 | 7.0 | High |
| Formal Shirt | L | 73 | 2 | 30 | 1.7 | 17.5 | Medium |
| Printed Top | XL | 44 | 1 | 32 | 1.9 | 17.2 | Medium |
| Cotton Kurti | L | 138 | 0 | 35 | 5.1 | 6.8 | Medium |

## Slow Stock / Markdown Priority
Review display/price first; markdown only if stock remains slow.
| Product | Units Sold | Revenue | Gross Margin (%) | Ending Stock | Days of Cover | Markdown Priority |
| --- | --- | --- | --- | --- | --- | --- |
| Scarf | 11 | 5,040 | 55.3% | 64 | 224.0 | High |
| Cap | 22 | 6,578 | 64.9% | 34 | 79.3 | High |
| Anarkali Kurta Set | 25 | 36,160 | 43.0% | 296 | 414.4 | High |
| Sling Bag | 29 | 20,271 | 59.2% | 35 | 81.7 | High |
| Kids Lehenga Set | 64 | 80,278 | 53.0% | 119 | 69.4 | High |
| Kids Ethnic Kurta Set | 97 | 96,903 | 57.0% | 148 | 45.0 | High |
| Ethnic Dupatta | 26 | 15,574 | 59.9% | 25 | 14.6 | Medium |
| Wallet | 30 | 14,970 | 60.9% | 35 | 35.0 | Medium |
| Handbag | 30 | 29,970 | 59.0% | 28 | 24.5 | Medium |
| Hair Accessories Set | 39 | 7,761 | 68.8% | 43 | 33.4 | Medium |

## AI Usage Transparency
Manager interpretation (maximum 180 words):
Basic Crew T-Shirt leads unit sales, while Scarf needs closer sell-through review. The clearest replenishment pressure is Cotton Kurti size M, with 26 stockout SKU-days and 9.2 days of cover. Saturday has the strongest average revenue per trading day. Female Adult segment over-indexes toward Ethnic Wear. Young Adult Female segment over-indexes toward Accessories. These customer patterns are merchandising test signals, not demographic truth.

- Python calculated all numbers and exactly three actions.
- AI, when configured, only interpreted verified facts.
- Model metadata: openai/gpt-oss-20b via Groq OpenAI-compatible API; temperature 0.2.
- A deterministic fallback is used when the API is not configured or unavailable.
- No API key or technical service detail is written to outputs.

## Limitations
- Stockout evidence is SKU-level and does not prove a whole size was unavailable or quantify lost sales.
- Slow movement can reflect demand, display, price, or stock depth; priority labels are review signals.
- Gross margin is estimated from available item cost data and is not net profit.
- Customer lift is association within one month, not causation or demographic truth.
