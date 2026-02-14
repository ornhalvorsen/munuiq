# Source Mapping — KS2 (Kanelsnurren)

## Sales Data

| Analytics Column | Source Table | Source Column | Notes |
|---|---|---|---|
| order_date | munu.orders | order_date | Business date |
| net_revenue | munu.order_lines | SUM(net_amount) | WHERE net_amount IS NOT NULL, excludes bundles |
| order_count | munu.orders | COUNT(DISTINCT soid) | WHERE state = 'completed' |
| revenue_unit_id | munu.orders | revenue_unit_id | Location join key |
| location_name | munu.revenue_units | name | Denormalized |

## Labor Data

| Analytics Column | Source Table | Source Column | Notes |
|---|---|---|---|
| actual_hours_worked | planday.punchclock_shifts | hours_worked | WHERE approved = true |
| scheduled_hours | planday.shifts | end - start (epoch/3600) | Duration in hours |
| overtime_hours | planday.punchclock_shifts | MAX(0, hours_worked - 7.5) | Per-shift threshold |
| headcount_present | planday.punchclock_shifts | COUNT(DISTINCT employee_id) | |
| hourly_rate | planday.pay_rates | hourly_rate | Fallback: salaries.effective_hourly_rate |
| role_name | planday.employee_groups | name | Filter: NOT LIKE 'Gammel%' |

## Location Bridge

| From | To | Join Path |
|---|---|---|
| punchclock_shifts | revenue_units | pc.department_id → department_mapping.planday_department_id → dm.munu_revenue_unit_id (or merged_into) |
| shifts | revenue_units | s.department_id → department_mapping → dm.munu_revenue_unit_id |

**Filter**: `dm.mapping_type = 'store'` (excludes production/admin departments)

## Absence Data (Planday)

| Shift Type Name Pattern | Standard Category | Notes |
|---|---|---|
| *egenmelding* | egenmelding | Self-certified sick (1-3 days) |
| *sykemeld*, *sykefrav* | sykemelding | Doctor-certified sick |
| *barn*, *sykt barn* | child_sick | Child illness |
| *ferie*, *permisjon* | vacation | Not counted as sick leave |
| Other absence types | other_absence | Catch-all |

**Discovery**: Run `--mode discover` to see actual shift_type names in the database.

## Cost Calculation

| Component | Formula |
|---|---|
| base_labor_cost | SUM(MIN(hours_worked, 7.5) * COALESCE(hourly_rate, effective_hourly_rate)) |
| overtime_cost | SUM(MAX(0, hours_worked - 7.5) * rate * 1.5) |
| total_labor_cost | base + overtime |
| labor_cost_pct | total_labor_cost / net_revenue * 100 |
