# Analytics Layer Playbook

## Implementation Checklist

1. **Connect** — Verify `connection.py` can reach munuiq database
2. **Discover** — Run `python -m app.analytics --mode discover` to map shift types and absence codes
3. **Review SOURCE_MAPPING** — Confirm table/column names match client data
4. **Daypart config** — Adjust hour boundaries if needed (default: Morning 06-11, Lunch 11-14, Afternoon 14-17, Evening 17-22)
5. **Product groups** — Seed from articles_unified categories; add custom group_sets if needed
6. **Labor/HR mapping** — Verify department_mapping covers all active stores; check pay_rate coverage
7. **Absence code mapping** — Map discovered shift_types to standard categories (egenmelding/sykemelding/child_sick)
8. **Sick leave config** — Set grunnbeløp, check IA-avtale status, configure egenmelding max days
9. **Tier 2 DDL + refresh** — Run `--mode full`; verify row counts
10. **Tier 3 metrics** — Built automatically during full refresh
11. **Validate** — Run validation queries (see below)
12. **CTXE context** — Verify analytics domain routing with test questions

## Reusable vs Client-Specific

### Reusable (same across deployments)
- All DDL (table schemas)
- Tier 3 SQL (trailing metrics, fleet benchmarks, percentiles)
- Pipeline orchestrator (`refresh.py`)
- CTXE integration (domain detection, routing, patterns)
- Norwegian sick leave rules (employer period, NAV split, 6G cap)
- Hourly staffing logic

### Client-Specific (varies per deployment)
- SOURCE_MAPPING (see `SOURCE_MAPPING.md`)
- Tier 2 SELECT statements (source table/column names)
- Daypart hour boundaries
- Product group definitions
- Labor data mapping (HR system bridge)
- Absence code mapping (varies by HR system)
- IA-avtale status
- Overtime rules (threshold, multiplier)
- Staffing targets

## Validation Queries

### Sales Integrity
```sql
-- Daily sales cube should match raw order_lines for a given date
SELECT
    (SELECT SUM(net_revenue) FROM analytics.daily_location_sales WHERE order_date = '2025-01-15') AS cube_revenue,
    (SELECT SUM(ol.net_amount) FROM "KS2-Service Agent Read".munu.orders o
     JOIN "KS2-Service Agent Read".munu.order_lines ol ON o.customer_id = ol.customer_id AND o.soid = ol.soid
     WHERE o.order_date = '2025-01-15' AND o.state = 'completed' AND ol.net_amount IS NOT NULL
       AND NOT regexp_matches(ol.article_name, '\d+.*\bfor\s+\d+')) AS raw_revenue;
```

### Labor Integrity
```sql
-- Labor cube hours should match raw punchclock for a given date
SELECT
    (SELECT SUM(actual_hours_worked) FROM analytics.daily_location_labor WHERE order_date = '2025-01-15') AS cube_hours,
    (SELECT SUM(pc.hours_worked) FROM "KS2-Service Agent Read".planday.punchclock_shifts pc
     JOIN "KS2-Service Agent Read".reference.department_mapping dm
       ON dm.planday_department_id = pc.department_id AND dm.planday_portal_name = pc.portal_name
     WHERE pc.date = '2025-01-15' AND pc.approved = true AND dm.mapping_type = 'store') AS raw_hours;
```

### Hourly Consistency
```sql
-- Hourly cube should sum to daily cube
SELECT
    h.order_date,
    SUM(h.actual_hours_in_hour) AS hourly_sum,
    d.actual_hours_worked AS daily_total,
    ABS(SUM(h.actual_hours_in_hour) - d.actual_hours_worked) AS diff
FROM analytics.daily_location_labor_hourly h
JOIN analytics.daily_location_labor d
    ON h.customer_id = d.customer_id AND h.revenue_unit_id = d.revenue_unit_id AND h.order_date = d.order_date
WHERE h.order_date = '2025-01-15'
GROUP BY h.order_date, h.revenue_unit_id, d.actual_hours_worked;
```

### Mix Validation
```sql
-- Revenue shares should sum to ~100% per location-day-group_set
SELECT customer_id, revenue_unit_id, order_date, group_set,
       ROUND(SUM(revenue_share_pct), 1) AS total_share
FROM analytics.daily_location_group_mix
WHERE order_date = '2025-01-15'
GROUP BY ALL
HAVING ABS(SUM(revenue_share_pct) - 100) > 1;
-- Should return 0 rows
```

### Fleet Benchmarks
```sql
-- P25 < median < P75
SELECT metric_name, fleet_p25, fleet_median, fleet_p75,
       CASE WHEN fleet_p25 <= fleet_median AND fleet_median <= fleet_p75 THEN 'OK' ELSE 'FAIL' END AS check
FROM analytics.fleet_benchmarks;
```

### Labor Metrics Sanity
```sql
-- transactions_per_labor_hour should be in range 3-20
SELECT revenue_unit_id, order_date, orders_per_labor_hour
FROM analytics.daily_location_labor
WHERE orders_per_labor_hour NOT BETWEEN 3 AND 20
  AND orders_per_labor_hour IS NOT NULL
LIMIT 10;
```

## Common Gotchas

### Labor
- **Overnight shifts**: Shifts spanning midnight are assigned to the clock-in date
- **Unpaid breaks**: `break_minutes` in punchclock_shifts — currently not deducted from hours
- **Multi-location employees**: Same employee can work different stores — each shift maps independently
- **Summer vikars**: Temporary staff may not have pay_rates — falls back to salaries table

### Sick Leave
- **16-day employer period**: Calendar days, not working days
- **Episode recurrence**: If employee returns and gets sick again within 16 days, employer period continues (not reset)
- **Grunnbeløp changes**: Updates May 1st annually — config_parameters has valid_from/valid_to
- **Gradert sykemelding**: Partial sick leave (e.g., 50%) — may need special handling
- **Egenmelding tracking**: May be incomplete in Planday — some absences logged as general sick leave
