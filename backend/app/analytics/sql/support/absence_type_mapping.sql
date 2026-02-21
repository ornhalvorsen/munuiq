-- Support: Absence Type Mapping
-- Maps planday.shift_types to standardized absence categories + cost bearers.
-- Seeded from ILIKE patterns matching discovery.py patterns.
--
-- absence_category: egenmelding, sykemelding, child_sick, vacation, other_absence
-- cost_bearer:
--   employer  — employer pays (egenmelding, arbeidsgiverperioden days 1-16, child sick)
--   nav       — NAV reimburses (sykemelding after day 16)
--   unpaid    — leave without pay
--   none      — not sick leave (vacation, permisjon) — excluded from sick rate

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.absence_type_mapping AS
WITH raw_mapping AS (
    SELECT
        st.portal_name,
        st.id        AS shift_type_id,
        st.name      AS shift_type_name,
        st.pay_percentage,
        CASE
            -- Egenmelding (self-certified sick leave, 1-3 days)
            WHEN st.name ILIKE '%egenmelding%'
              OR st.name ILIKE '%egen meld%'
            THEN 'egenmelding'

            -- Sykemelding (doctor-certified sick leave)
            WHEN st.name ILIKE '%sykemeld%'
              OR st.name ILIKE '%sykefrav%'
              OR st.name ILIKE '%syke frav%'
            THEN 'sykemelding'

            -- Child sick / care days
            WHEN st.name ILIKE '%barn%'
              OR st.name ILIKE '%sykt barn%'
              OR st.name ILIKE '%omsorg%'
            THEN 'child_sick'

            -- Vacation / leave (not sick leave)
            WHEN st.name ILIKE '%ferie%'
              OR st.name ILIKE '%permisjon%'
            THEN 'vacation'

            -- Other absence (generic sick / absence)
            WHEN st.name ILIKE '%syk%'
              OR st.name ILIKE '%fravær%'
              OR st.name ILIKE '%absence%'
              OR st.name ILIKE '%leave%'
              OR st.name ILIKE '%permitt%'
            THEN 'other_absence'

            ELSE NULL
        END AS absence_category
    FROM {SOURCE_DB}.planday.shift_types st
)
SELECT
    rm.portal_name,
    rm.shift_type_id,
    rm.shift_type_name,
    rm.pay_percentage,
    rm.absence_category,
    CASE
        -- Vacation / permisjon — not part of sick rate
        WHEN rm.absence_category = 'vacation'
        THEN 'none'

        -- Unpaid leave
        WHEN rm.shift_type_name ILIKE '%uten lønn%'
          OR rm.shift_type_name ILIKE '%uten lonn%'
        THEN 'unpaid'

        -- NAV pays: sykemelding with 0% pay (NAV period, day 17+)
        WHEN rm.absence_category = 'sykemelding'
          AND COALESCE(rm.pay_percentage, 0) = 0
        THEN 'nav'

        -- Employer pays: egenmelding (always employer)
        WHEN rm.absence_category = 'egenmelding'
        THEN 'employer'

        -- Employer pays: sykemelding arbeidsgiverperioden (days 1-16)
        WHEN rm.absence_category = 'sykemelding'
          AND COALESCE(rm.pay_percentage, 0) > 0
        THEN 'employer'

        -- Child sick — always employer-borne
        WHEN rm.absence_category = 'child_sick'
        THEN 'employer'

        -- Other absence — employer by default
        WHEN rm.absence_category = 'other_absence'
        THEN 'employer'

        ELSE 'employer'
    END AS cost_bearer
FROM raw_mapping rm
WHERE rm.absence_category IS NOT NULL;
