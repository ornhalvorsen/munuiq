# Source Mapping Template

Use this template when onboarding a new client to the analytics layer.

## Client Information

- **Client name**: ___
- **customer_id(s)**: ___
- **POS system**: ___
- **HR/workforce system**: ___

## Sales Data Mapping

| Analytics Column | Source Table | Source Column | Filter/Transform |
|---|---|---|---|
| order_date | ___.orders | ___ | Business date column |
| net_revenue | ___.order_lines | ___ | Revenue excl VAT. NULL = bundle? |
| order_count | ___.orders | ___ | Which state = completed? |
| revenue_unit_id | ___.orders | ___ | Location join key |
| location_name | ___.locations | ___ | Display name |
| article_id | ___.order_lines | ___ | Product FK |
| category | ___.articles | ___ | Product category |

**Bundle handling**: How does the POS handle multi-item bundles?
- [ ] Dual line items (bundle SKU + components)
- [ ] Single line item per bundle
- [ ] No bundles

## Labor / Time Registration

| Analytics Column | Source Table | Source Column | Notes |
|---|---|---|---|
| actual_hours_worked | ___ | ___ | Approved/clocked hours |
| scheduled_hours | ___ | ___ | Planned shift hours |
| employee_id | ___ | ___ | Unique employee identifier |
| department/location | ___ | ___ | How shifts map to locations |
| clock_in / clock_out | ___ | ___ | For hourly proration |

**Location bridge**: How do HR departments map to POS locations?
- Bridge table: ___
- Join key: ___
- Filter for store-only: ___

## Wage / Rate Data

| Analytics Column | Source Table | Source Column | Notes |
|---|---|---|---|
| hourly_rate | ___ | ___ | Hourly pay rate |
| employee_group | ___ | ___ | Role/position name |
| overtime_multiplier | ___ | ___ | Default: 1.5x |
| monthly_salary | ___ | ___ | For salaried employees |
| effective_hourly_rate | ___ | ___ | Salary / standard hours |

**Pay rate coverage**: What % of employees have pay rate data?
- [ ] >90% — good
- [ ] 50-90% — need salary fallback
- [ ] <50% — may need manual rate table

## Absence Data

| Source Code/Type | Standard Category | Count (discovery) |
|---|---|---|
| ___ | egenmelding | ___ |
| ___ | sykemelding | ___ |
| ___ | child_sick | ___ |
| ___ | vacation | ___ |
| ___ | other_absence | ___ |

**Absence tracking method**:
- [ ] Separate shift type in scheduling system
- [ ] Absence module in HR system
- [ ] Manual tracking
- [ ] Not tracked digitally

## Sick Leave Configuration

| Parameter | Value | Notes |
|---|---|---|
| IA-avtale (Inkluderende Arbeidsliv) | Yes / No | Affects egenmelding days |
| Max egenmelding days (per episode) | 3 (standard) / 8 (IA) | |
| Max egenmelding episodes per year | 4 (standard) / varies | |
| Employer period (sykemelding) | 16 calendar days | Standard Norwegian law |
| Grunnbeløp (1G) | See config_parameters | Updates May 1st |
| Employees above 6G salary | ___ count | NAV reimburses up to 6G only |

## Daypart Configuration

| Daypart | Start Hour | End Hour | Adjust? |
|---|---|---|---|
| Morning | 06 | 11 | |
| Lunch | 11 | 14 | |
| Afternoon | 14 | 17 | |
| Evening | 17 | 22 | |

## Product Groupings

Beyond standard category/subcategory from articles_unified:
- Custom group_set 1: ___
- Custom group_set 2: ___

## Staffing Targets

| Location Type | Target Transactions/Staff/Hour | Notes |
|---|---|---|
| Standard store | 10 | Default |
| High-volume | ___ | |
| Café format | ___ | |
