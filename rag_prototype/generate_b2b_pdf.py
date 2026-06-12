"""
generate_b2b_pdf.py -- Creates novaspark_b2b_services.pdf in rag_prototype/data/
Run once: python generate_b2b_pdf.py
"""

from fpdf import FPDF, XPos, YPos
import os

OUTPUT = os.path.join(os.path.dirname(__file__), "data", "novaspark_b2b_services.pdf")


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, "NovaSpark Technologies  |  B2B Services & Products Catalogue  |  2025",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.ln(2)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, f"Page {self.page_no()}  |  sales@novaspark.io  |  novaspark.io/demo", align="C")

    def section_title(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(30, 100, 200)
        self.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(30, 100, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def sub_title(self, title: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(50, 50, 50)
        self.cell(0, 7, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)

    def body(self, text: str):
        self.set_font("Helvetica", size=10)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bullet(self, items: list):
        self.set_font("Helvetica", size=10)
        indent = 10
        page_w = self.w - self.l_margin - self.r_margin
        for item in items:
            self.cell(indent, 5.5, "* ")
            self.multi_cell(page_w - indent, 5.5, item)
        self.ln(1)

    def price_row(self, tier, price, users, volume, sla):
        col = [38, 38, 38, 38, 38]
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(240, 245, 255)
        self.cell(col[0], 7, tier, border=1, fill=True)
        self.set_font("Helvetica", size=9)
        self.cell(col[1], 7, price, border=1)
        self.cell(col[2], 7, users, border=1)
        self.cell(col[3], 7, volume, border=1)
        self.cell(col[4], 7, sla, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def price_header(self):
        col = [38, 38, 38, 38, 38]
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(30, 100, 200)
        self.set_text_color(255, 255, 255)
        for i, (label, w) in enumerate(zip(["Tier", "Monthly Price", "Users", "Volume", "Uptime SLA"], col)):
            if i == len(col) - 1:
                self.cell(w, 7, label, border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                self.cell(w, 7, label, border=1, fill=True)
        self.set_text_color(0, 0, 0)


pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=16)
pdf.add_page()

# Cover / Intro
pdf.ln(6)
pdf.set_font("Helvetica", "B", 22)
pdf.set_text_color(30, 100, 200)
pdf.cell(0, 12, "NovaSpark Technologies", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
pdf.set_font("Helvetica", "B", 14)
pdf.set_text_color(60, 60, 60)
pdf.cell(0, 8, "B2B Services & Products Catalogue  |  2025 Edition",
         new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
pdf.set_text_color(0, 0, 0)
pdf.ln(4)

pdf.body(
    "NovaSpark Technologies is a B2B software company founded in 2017 and headquartered in Austin, "
    "Texas. We deliver AI-powered data infrastructure tools that help mid-market and enterprise teams "
    "ingest, process, and act on their data in real time. Serving 1,400+ customers across North "
    "America, Europe, and Asia-Pacific, NovaSpark is the trusted data platform for teams that need "
    "reliability, scale, and developer-first tooling."
)

# Product Overview
pdf.section_title("Product Overview")
pdf.body(
    "NovaSpark offers five integrated products, each available standalone or as part of the "
    "NovaSpark Platform Bundle (30% discount when all five are purchased together)."
)

# SparkStream
pdf.section_title("1. SparkStream - Real-Time Data Pipeline")
pdf.body(
    "SparkStream is NovaSpark's flagship product: a fully managed, serverless event-streaming "
    "platform built on Apache Kafka. It handles ingestion, transformation, and routing of event "
    "data at up to 10 million events per second per tenant with sub-100 ms end-to-end latency at p99."
)
pdf.sub_title("Key Features")
pdf.bullet([
    "200+ pre-built connectors: Salesforce, Snowflake, PostgreSQL, S3, Webhook, and more.",
    "Sub-100 ms end-to-end latency at p99.",
    "Schema registry with auto-evolution and backward-compatibility checks.",
    "Built-in dead-letter queue and automatic retry with exponential backoff.",
    "Exactly-once delivery semantics across all connectors.",
    "Visual drag-and-drop pipeline builder plus full Terraform provider.",
    "Kafka-compatible API -- migrate existing Kafka workloads with zero code changes.",
])
pdf.sub_title("Pricing")
pdf.price_header()
pdf.price_row("Starter", "$499 / mo", "Up to 5", "10M events/mo", "99.9%")
pdf.price_row("Professional", "$1,999 / mo", "Up to 25", "200M events/mo", "99.95%")
pdf.price_row("Enterprise", "Custom", "Unlimited", "Custom commit", "99.99%")
pdf.ln(2)
pdf.body("Overage (Starter & Professional): $0.12 per additional million events.")

# SparkDB
pdf.section_title("2. SparkDB - Analytical Data Warehouse")
pdf.body(
    "SparkDB is a columnar, ANSI-SQL analytical data warehouse optimised for workloads that mix "
    "batch reporting with interactive BI queries. Compute and storage are separated, so teams can "
    "pause clusters and pay only for storage when idle."
)
pdf.sub_title("Key Features")
pdf.bullet([
    "Petabyte-scale storage on S3-compatible object storage.",
    "Automatic workload isolation: separate compute clusters per team.",
    "Time-travel queries: restore any table to any point in the last 90 days.",
    "Native integrations with dbt, Apache Spark, and Jupyter.",
    "Row-level security and column masking built in.",
    "Query result cache with configurable TTL.",
    "Paused clusters incur zero compute costs.",
])
pdf.sub_title("Pricing")
pdf.price_header()
pdf.price_row("Starter", "$499 / mo", "Up to 5", "50 GB storage", "99.9%")
pdf.price_row("Professional", "$1,999 / mo", "Up to 25", "500 GB storage", "99.95%")
pdf.price_row("Enterprise", "Custom", "Unlimited", "Custom commit", "99.99%")
pdf.ln(2)
pdf.body("Compute billed per vCPU-hour on active query clusters. Storage billed per GB-month (compressed).")

# SparkML
pdf.section_title("3. SparkML - Machine Learning Platform")
pdf.body(
    "SparkML is an end-to-end MLOps platform that takes teams from feature engineering to model "
    "serving without leaving the NovaSpark ecosystem. GPU-accelerated training and one-click "
    "deployment remove infrastructure bottlenecks so data scientists can focus on models."
)
pdf.sub_title("Key Features")
pdf.bullet([
    "Managed feature store with point-in-time correct joins.",
    "AutoML for classification, regression, and time-series forecasting.",
    "GPU-accelerated training clusters (H100 and A100) with spot pricing.",
    "One-click model deployment as REST endpoint or batch inference job.",
    "Experiment tracking with MLflow-compatible API.",
    "Drift detection and automated re-training triggers.",
    "Integrated with SparkDB and SparkStream for live feature pipelines.",
])
pdf.sub_title("Pricing")
pdf.price_header()
pdf.price_row("Starter", "$499 / mo", "Up to 5", "CPU training only", "99.9%")
pdf.price_row("Professional", "$1,999 / mo", "Up to 25", "A100 GPU access", "99.95%")
pdf.price_row("Enterprise", "Custom", "Unlimited", "H100 + spot pools", "99.99%")
pdf.ln(2)
pdf.body("GPU training billed per GPU-hour at spot or on-demand rates. Inference endpoints billed per million requests.")

# SparkGovernance
pdf.section_title("4. SparkGovernance - Data Catalog & Lineage")
pdf.body(
    "SparkGovernance gives data teams a single pane of glass over all their data assets: tables, "
    "dashboards, ML models, and pipelines. It automatically harvests metadata and builds a "
    "column-level lineage graph so teams always know where data comes from and who owns it."
)
pdf.sub_title("Key Features")
pdf.bullet([
    "Automated metadata harvesting via passive query-log analysis (no agents required).",
    "Column-level lineage graph rendered as an interactive DAG.",
    "Business glossary with ownership and certification workflows.",
    "PII classification and GDPR / CCPA compliance reporting.",
    "Integration with Jira and Slack for data-quality incident routing.",
    "Policy-based access control tied directly to catalog classifications.",
])
pdf.sub_title("Pricing")
pdf.price_header()
pdf.price_row("Starter", "$499 / mo", "Up to 5", "Up to 500 assets", "99.9%")
pdf.price_row("Professional", "$1,999 / mo", "Up to 25", "Up to 10K assets", "99.95%")
pdf.price_row("Enterprise", "Custom", "Unlimited", "Unlimited assets", "99.99%")

# SparkAlert
pdf.section_title("5. SparkAlert - Anomaly Detection & Observability")
pdf.body(
    "SparkAlert monitors data pipelines and warehouse queries for anomalies, SLA breaches, and cost "
    "spikes -- alerting the right person before downstream consumers notice a problem. ML-based "
    "detection requires zero manual threshold-setting."
)
pdf.sub_title("Key Features")
pdf.bullet([
    "ML-based anomaly detection with zero manual threshold-setting.",
    "Freshness, volume, schema, and distribution monitors out of the box.",
    "PagerDuty, OpsGenie, Slack, and email integrations.",
    "Cost anomaly detection: flags when a query or pipeline exceeds budget.",
    "Root-cause analysis assistant powered by LLM.",
    "SLA breach alerts with downstream impact analysis.",
])
pdf.sub_title("Pricing")
pdf.price_header()
pdf.price_row("Starter", "$499 / mo", "Up to 5", "Up to 50 monitors", "99.9%")
pdf.price_row("Professional", "$1,999 / mo", "Up to 25", "Up to 500 monitors", "99.95%")
pdf.price_row("Enterprise", "Custom", "Unlimited", "Unlimited monitors", "99.99%")

# Platform Bundle
pdf.section_title("Platform Bundle - All 5 Products at 30% Off")
pdf.body(
    "Purchase all five NovaSpark products together and receive a 30% discount off the sum of "
    "individual list prices. The bundle includes unified billing, a single Customer Success Manager, "
    "and cross-product dashboards."
)
pdf.bullet([
    "Starter Bundle: ~$1,747 / mo  (5 products x $499 x 0.70)",
    "Professional Bundle: ~$6,997 / mo  (5 products x $1,999 x 0.70)",
    "Enterprise Bundle: Custom pricing -- contact sales@novaspark.io",
])

# Security & Compliance
pdf.section_title("Security & Compliance")
pdf.bullet([
    "SOC 2 Type II -- annual third-party audit; report available on request.",
    "ISO 27001 certified since 2022.",
    "GDPR and CCPA compliant; DPA available on Enterprise plan.",
    "HIPAA Business Associate Agreement available for Enterprise customers.",
    "All data encrypted at rest (AES-256) and in transit (TLS 1.3).",
    "Customer-managed encryption keys (CMEK) on Enterprise.",
    "Role-based (RBAC) and attribute-based (ABAC) access control.",
    "MFA enforced for all accounts; SSO via SAML 2.0 and OIDC (Professional+).",
    "VPC peering and AWS PrivateLink on Enterprise.",
    "Quarterly penetration tests; bug-bounty programme via HackerOne.",
])

# B2B Professional Services Add-Ons
pdf.section_title("B2B Professional Services Add-Ons")

pdf.sub_title("Implementation & Onboarding")
pdf.body(
    "Dedicated implementation engineers guide your team from sign-up to production. "
    "Typical engagement: 4-8 weeks."
)
pdf.bullet([
    "Starter / Professional: self-serve onboarding + documentation portal.",
    "Enterprise: dedicated implementation engineer, architecture review, and go-live support.",
    "Custom data migration packages available -- contact sales for scoping.",
])

pdf.sub_title("Training & Enablement")
pdf.bullet([
    "On-demand video library: 100+ hours of product training (all plans, free).",
    "Instructor-led virtual workshops: $2,500 per full-day session (up to 20 attendees).",
    "On-site training at customer locations: $5,000 per day + travel (Enterprise).",
    "NovaSpark Certified Engineer certification exam: $200 per candidate.",
])

pdf.sub_title("Managed Services")
pdf.bullet([
    "Pipeline Management: NovaSpark SRE team manages your SparkStream pipelines. From $3,000/mo.",
    "Data Modelling: NovaSpark analysts build and maintain your SparkDB data models. From $4,500/mo.",
    "ML Operations: Managed model monitoring, retraining, and deployment. From $5,000/mo.",
])

# Support Tiers
pdf.section_title("Support Tiers")
pdf.bullet([
    "Starter  -- Community forum, documentation portal (docs.novaspark.io). 99.9% SLA.",
    "Professional  -- Email + in-app chat, business hours, 4-hour first response. 99.95% SLA.",
    "Enterprise  -- 24/7 phone & Slack Connect, named CSM, 1-hour critical response. 99.99% SLA.",
])

# Contact & Next Steps
pdf.section_title("Contact & Next Steps")
pdf.body(
    "Every product includes a 14-day free trial with full functionality and no credit card required. "
    "Trials can be extended to 30 days on request."
)
pdf.bullet([
    "Book a personalised demo:  novaspark.io/demo",
    "Sales enquiries:  sales@novaspark.io",
    "Partner programme:  partners@novaspark.io",
    "Support:  support@novaspark.io  |  +1-800-NOVA-SPK (Enterprise)",
    "Headquarters:  500 Congress Ave, Suite 2200, Austin, TX 78701, USA",
])

pdf.output(OUTPUT)
print(f"PDF written to: {OUTPUT}")
