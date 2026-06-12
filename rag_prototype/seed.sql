-- ERP demo schema for the NushadLabs RAG prototype.
-- Loaded automatically by the Postgres container on first start.

CREATE TABLE IF NOT EXISTS products (
    id           SERIAL PRIMARY KEY,
    tenant_id    INTEGER          NOT NULL,
    name         TEXT             NOT NULL,
    description  TEXT             NOT NULL DEFAULT '',
    price        NUMERIC(10, 2)   NOT NULL,
    discount_pct NUMERIC(5,  2)   NOT NULL DEFAULT 0,
    category     TEXT             NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    demand_score NUMERIC(4,  2)   NOT NULL DEFAULT 0,
    stock        INTEGER          NOT NULL DEFAULT 0
);

-- Auto-bump updated_at on every UPDATE so incremental sync can detect changes.
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS set_updated_at ON products;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();

-- ── Tenant 1 · NovaSpark Technologies (B2B data infrastructure & AI) ─────────

INSERT INTO products (tenant_id, name, description, price, discount_pct, category, created_at, updated_at, demand_score, stock) VALUES
(1, 'DataPulse Analytics Platform',
 'Enterprise real-time analytics platform with customisable dashboards and ML-powered anomaly detection. Processes up to 1 million events per second.',
 2499.00, 10.00, 'Software',
 '2025-01-10 09:00:00+00', '2025-01-10 09:00:00+00', 8.5, 50),

(1, 'CloudSync Pro',
 'Automated multi-cloud synchronisation and incremental backup solution with end-to-end AES-256 encryption and policy-driven retention.',
 999.00, 0.00, 'Software',
 '2025-01-10 09:05:00+00', '2025-01-10 09:05:00+00', 7.2, 100),

(1, 'SecureVault HSM',
 'FIPS 140-3 Level 3 hardware security module for enterprise cryptographic key management, certificate storage, and digital signing operations.',
 4999.00, 5.00, 'Hardware',
 '2025-02-14 11:00:00+00', '2025-02-14 11:00:00+00', 6.8, 15),

(1, 'API Gateway Enterprise',
 'High-throughput API gateway with OAuth 2.0, JWT validation, rate limiting, and real-time usage dashboards. Handles 50k requests per second per node.',
 599.00, 15.00, 'Software',
 '2025-02-20 14:30:00+00', '2025-02-20 14:30:00+00', 9.1, 200),

(1, 'AI Knowledge Assistant',
 'Conversational AI toolkit for building internal knowledge-base Q&A systems. Supports PDF, DOCX, and SQL ingestion pipelines out of the box.',
 1499.00, 0.00, 'Software',
 '2025-03-05 10:00:00+00', '2025-03-05 10:00:00+00', 8.9, 75),

(1, 'DataBridge ETL Pipeline',
 'Low-code ETL pipeline builder for connecting relational databases, SaaS APIs, and data warehouses. Includes 200+ pre-built connectors.',
 799.00, 5.00, 'Software',
 '2025-03-15 08:45:00+00', '2025-03-15 08:45:00+00', 7.5, 80),

(1, 'NovaSpark Premium Support',
 '24/7 enterprise technical support with a guaranteed 1-hour response SLA for Severity-1 incidents and a dedicated account engineer.',
 299.00, 0.00, 'Services',
 '2025-04-01 09:00:00+00', '2025-04-01 09:00:00+00', 5.2, 500),

(1, 'ServerShield NGFW Appliance',
 'Next-generation firewall with deep-packet inspection, TLS 1.3 decryption, and integrated IDS/IPS. Throughput: 40 Gbps.',
 7999.00, 0.00, 'Hardware',
 '2025-04-10 12:00:00+00', '2025-04-10 12:00:00+00', 6.1, 20),

(1, 'ML Training GPU Cluster (hourly)',
 'On-demand high-performance GPU cluster (8× NVIDIA A100 80 GB) for distributed machine learning training. Per-hour billing, no minimum commitment.',
 199.00, 20.00, 'Cloud',
 '2025-05-01 07:00:00+00', '2025-05-01 07:00:00+00', 8.3, 1000),

(1, 'Compliance Audit Toolkit',
 'Automated compliance audit and report generation for SOC 2, GDPR, ISO 27001, and HIPAA. Integrates with Jira, Slack, and email for findings.',
 449.00, 10.00, 'Software',
 '2025-05-20 09:30:00+00', '2025-05-20 09:30:00+00', 7.0, 60),

(1, 'DataLake Object Storage',
 'Petabyte-scale S3-compatible object storage for data lakes. Features intelligent tiering, lifecycle policies, and built-in versioning.',
 89.00, 0.00, 'Cloud',
 '2025-06-05 11:00:00+00', '2025-06-05 11:00:00+00', 7.8, 5000),

(1, 'VPN Gateway Pro',
 'Enterprise VPN with SAML SSO, split tunnelling, and a 99.99% uptime SLA. Scales to 50,000 concurrent users without hardware changes.',
 299.00, 10.00, 'Software',
 '2025-07-01 10:00:00+00', '2025-07-01 10:00:00+00', 6.5, 150),

(1, 'Custom AI Model Development',
 'Bespoke machine learning model design, training, evaluation, and production deployment by NovaSpark senior ML engineers. Fixed-price engagement.',
 15000.00, 0.00, 'Services',
 '2025-08-15 09:00:00+00', '2025-08-15 09:00:00+00', 9.5, 10),

(1, 'Edge Computing IoT Node',
 'Ruggedised edge computing device for real-time IoT data processing at the network edge. ARM Cortex-A72, 8 GB RAM, IP67-rated enclosure.',
 1299.00, 5.00, 'Hardware',
 '2025-09-10 08:00:00+00', '2025-09-10 08:00:00+00', 7.3, 30),

(1, 'Data Quality Monitor',
 'Continuous automated data quality monitoring with statistical anomaly detection, schema drift alerts, and Slack/Teams/PagerDuty integrations.',
 399.00, 15.00, 'Software',
 '2026-05-01 07:00:00+00', '2026-05-01 07:00:00+00', 8.0, 90),

-- ── Tenant 2 · FreshMart Grocery Co. (regional grocery & home delivery) ──────

(2, 'Organic Hass Avocados (Pack of 6)',
 'Hand-picked organic Hass avocados from certified Fairtrade farms in Peru. Ready-to-eat ripeness. Naturally waterproof skin, low price per unit.',
 7.99, 0.00, 'Produce',
 '2025-01-08 06:00:00+00', '2025-01-08 06:00:00+00', 8.7, 200),

(2, 'Cold-Pressed Extra Virgin Olive Oil 1L',
 'Single-origin Italian cold-pressed extra virgin olive oil with <0.2% acidity. Harvested by hand, rich in polyphenols and healthy fats.',
 14.99, 5.00, 'Pantry',
 '2025-01-08 06:05:00+00', '2025-01-08 06:05:00+00', 7.4, 150),

(2, 'Waterproof Insulated Cooler Bag',
 'Reusable waterproof insulated grocery bag with food-safe PE foam lining. Keeps items cold for 8 hours. Folds flat for easy storage.',
 19.99, 20.00, 'Accessories',
 '2025-02-01 08:00:00+00', '2025-02-01 08:00:00+00', 6.2, 80),

(2, 'Free-Range Eggs (Dozen)',
 'Farm-fresh Grade A large free-range eggs from pasture-raised hens. No antibiotics, no hormones. Collected daily and refrigerated immediately.',
 5.49, 0.00, 'Dairy & Eggs',
 '2025-02-10 07:00:00+00', '2025-02-10 07:00:00+00', 9.1, 300),

(2, 'Unsweetened Oat Milk 1L',
 'Creamy barista-grade oat milk made from whole-grain oats, unsweetened and fortified with vitamin D and calcium. Froths well for coffee.',
 3.99, 10.00, 'Beverages',
 '2025-03-01 06:30:00+00', '2025-03-01 06:30:00+00', 8.3, 250),

(2, 'Artisan Sourdough Loaf 800g',
 'Freshly baked 72-hour cold-fermented sourdough made with stoneground flour and live culture starter. Crispy crust, open chewy crumb.',
 6.99, 0.00, 'Bakery',
 '2025-03-15 05:00:00+00', '2025-03-15 05:00:00+00', 9.0, 60),

(2, 'Organic Baby Spinach 200g',
 'Triple-washed tender organic baby spinach leaves, ready to eat. Grown without synthetic pesticides. High in iron and folate.',
 3.49, 0.00, 'Produce',
 '2025-04-05 06:00:00+00', '2025-04-05 06:00:00+00', 7.9, 180),

(2, 'Wild-Caught Atlantic Salmon Fillet 300g',
 'Sustainably sourced wild-caught Atlantic salmon, skinless and boneless. Frozen at sea within 4 hours of catch to lock in freshness.',
 12.99, 10.00, 'Seafood',
 '2025-04-20 07:00:00+00', '2025-04-20 07:00:00+00', 8.5, 40),

(2, 'Frozen Mixed Berry Smoothie Pack 500g',
 'IQF blend of strawberries, blueberries, raspberries, and blackberries. No added sugar or preservatives. Ready straight from freezer to blender.',
 8.99, 5.00, 'Frozen',
 '2025-05-10 06:00:00+00', '2025-05-10 06:00:00+00', 7.6, 120),

(2, 'Full-Fat Greek Yogurt 500g',
 'Traditional strained full-fat Greek yogurt with 10% fat content. Made from whole milk with live cultures. No thickeners or additives.',
 4.99, 0.00, 'Dairy & Eggs',
 '2025-05-25 07:00:00+00', '2025-05-25 07:00:00+00', 8.8, 160),

(2, '85% Dark Chocolate Bar 100g',
 'Belgian stone-ground single-origin 85% dark chocolate. Naturally sweetened with unrefined coconut sugar. Vegan and gluten-free.',
 3.49, 15.00, 'Snacks',
 '2025-06-10 08:00:00+00', '2025-06-10 08:00:00+00', 7.1, 220),

(2, 'Free-Range Chicken Breast 500g',
 'Boneless skinless free-range chicken breast from antibiotic-free, hormone-free birds. Individually vacuum-sealed for freshness.',
 9.99, 0.00, 'Meat',
 '2025-07-01 06:00:00+00', '2025-07-01 06:00:00+00', 9.3, 90),

(2, 'Stainless Steel Water Bottle 1L',
 'Double-walled vacuum-insulated BPA-free stainless steel water bottle. Keeps drinks cold 24h or hot 12h. Leak-proof lid, dishwasher-safe.',
 24.99, 25.00, 'Accessories',
 '2025-08-05 09:00:00+00', '2025-08-05 09:00:00+00', 6.8, 50),

(2, 'Organic White Quinoa 500g',
 'Pre-washed certified organic whole-grain white quinoa. Complete protein source with all nine essential amino acids. Cooks in 15 minutes.',
 7.49, 0.00, 'Grains & Pasta',
 '2025-09-01 08:00:00+00', '2025-09-01 08:00:00+00', 7.2, 140),

(2, 'Raw Kombucha Original 330ml',
 'Naturally fermented raw kombucha brewed with green tea, apple cider vinegar, and live SCOBY cultures. Low sugar, no pasteurisation.',
 3.99, 0.00, 'Beverages',
 '2026-05-01 07:00:00+00', '2026-05-01 07:00:00+00', 7.8, 200);
