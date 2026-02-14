-- Product group definitions: map articles to custom groups
-- Bootstrap from articles_unified categories

CREATE OR REPLACE TABLE {TARGET_SCHEMA}.product_group_definitions (
    customer_id  INTEGER NOT NULL,
    article_id   VARCHAR NOT NULL,
    group_set    VARCHAR NOT NULL,
    group_value  VARCHAR NOT NULL,
    PRIMARY KEY (customer_id, article_id, group_set)
);

-- Seed from articles_unified categories
INSERT INTO {TARGET_SCHEMA}.product_group_definitions
SELECT
    au.customer_id,
    au.article_id,
    'category' AS group_set,
    au.category AS group_value
FROM {SOURCE_DB}.munu.articles_unified au
WHERE au.category_is_active = true
  AND au.category IS NOT NULL;

-- Also seed subcategory groupings
INSERT INTO {TARGET_SCHEMA}.product_group_definitions
SELECT
    au.customer_id,
    au.article_id,
    'subcategory' AS group_set,
    au.subcategory AS group_value
FROM {SOURCE_DB}.munu.articles_unified au
WHERE au.category_is_active = true
  AND au.subcategory IS NOT NULL;
