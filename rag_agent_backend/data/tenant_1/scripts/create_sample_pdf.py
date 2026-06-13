"""
create_sample_pdf.py — Generates data/company_knowledge.pdf using fpdf2.
Run once: python create_sample_pdf.py
"""

from pathlib import Path
from fpdf import FPDF

PAGES = [
    # ── Page 1: Overview & Mission ──────────────────────────────────────────
    {
        "sections": [
            {
                "heading": "NovaSpark Technologies — Company Overview",
                "body": (
                    "NovaSpark Technologies is a B2B software company founded in 2017 and "
                    "headquartered in Austin, Texas. We specialise in AI-powered data "
                    "infrastructure tools that help mid-market and enterprise teams ingest, "
                    "process, and act on their data in real time. As of 2025 we serve over "
                    "1,400 customers across North America, Europe, and the Asia-Pacific region, "
                    "ranging from 50-person scale-ups to Fortune 500 organisations.\n\n"
                    "Our engineering team of 280 employees ships weekly releases across five "
                    "product lines. We are a remote-first company with offices in Austin (HQ), "
                    "London, and Singapore."
                ),
            },
            {
                "heading": "Mission & Vision",
                "body": (
                    "Mission: Empower every data team to make confident decisions at the speed "
                    "of their business.\n\n"
                    "Vision: A world where latency between raw data and business insight is "
                    "measured in seconds, not days.\n\n"
                    "Core values:\n"
                    "  • Transparency — we publish our roadmap publicly and hold monthly "
                    "town-halls with customers.\n"
                    "  • Reliability — we target 99.95% uptime across all managed services and "
                    "compensate customers automatically when SLAs are missed.\n"
                    "  • Developer-first — every feature ships with a CLI, an API, and a UI so "
                    "teams can integrate however they prefer."
                ),
            },
            {
                "heading": "Company History",
                "body": (
                    "2017 - NovaSpark founded by Elena Okafor and James Tran after four years "
                    "at a major cloud provider. Seed round of $3.2 M closed.\n\n"
                    "2019 - Series A ($18 M). SparkStream v1 launched, signing 120 customers "
                    "in the first six months.\n\n"
                    "2021 - Series B ($65 M). Acquired DataVault Inc. to add encryption-at-rest "
                    "and key-management capabilities to the platform.\n\n"
                    "2023 - Series C ($140 M). Expanded to EMEA and APAC. Launched SparkML "
                    "and SparkGovernance. ARR crossed $42 M.\n\n"
                    "2025 - 1,400+ customers, 280 employees, ARR of $89 M."
                ),
            },
        ]
    },

    # ── Page 2: Product Catalog ──────────────────────────────────────────────
    {
        "sections": [
            {
                "heading": "Product Catalog",
                "body": (
                    "NovaSpark offers five integrated products. Each can be purchased "
                    "standalone or as part of the NovaSpark Platform bundle."
                ),
            },
            {
                "heading": "1. SparkStream — Real-Time Data Pipeline",
                "body": (
                    "SparkStream is our flagship product: a fully managed, serverless event "
                    "streaming platform built on Apache Kafka under the hood. It handles "
                    "ingestion, transformation, and routing of event data at up to 10 million "
                    "events per second per tenant.\n\n"
                    "Key features:\n"
                    "  • 200+ pre-built connectors (Salesforce, Snowflake, PostgreSQL, S3, "
                    "Webhook, and more).\n"
                    "  • Sub-100 ms end-to-end latency at p99.\n"
                    "  • Schema registry with auto-evolution and backward compatibility checks.\n"
                    "  • Built-in dead-letter queue and automatic retry with exponential backoff.\n"
                    "  • Exactly-once delivery semantics across all connectors.\n"
                    "  • Visual pipeline builder (drag-and-drop) and full Terraform provider."
                ),
            },
            {
                "heading": "2. SparkDB — Analytical Data Warehouse",
                "body": (
                    "SparkDB is a columnar, ANSI-SQL analytical database optimised for "
                    "workloads that mix batch reporting with interactive BI queries. It "
                    "separates compute and storage, allowing teams to pause clusters and pay "
                    "only for storage when idle.\n\n"
                    "Key features:\n"
                    "  • Petabyte-scale storage on object storage (S3-compatible).\n"
                    "  • Automatic workload isolation: separate compute clusters per team.\n"
                    "  • Time-travel queries: restore any table to any point in the last 90 days.\n"
                    "  • Native integrations with dbt, Apache Spark, and Jupyter.\n"
                    "  • Row-level security and column masking built in.\n"
                    "  • Query result cache with configurable TTL."
                ),
            },
            {
                "heading": "3. SparkML — Machine Learning Platform",
                "body": (
                    "SparkML is an end-to-end MLOps platform that takes teams from feature "
                    "engineering to model serving without leaving the NovaSpark ecosystem.\n\n"
                    "Key features:\n"
                    "  • Managed feature store with point-in-time correct joins.\n"
                    "  • AutoML for classification, regression, and time-series forecasting.\n"
                    "  • GPU-accelerated training clusters (H100 and A100) with spot pricing.\n"
                    "  • One-click model deployment as REST endpoint or batch inference job.\n"
                    "  • Experiment tracking (MLflow-compatible API).\n"
                    "  • Drift detection and automated re-training triggers."
                ),
            },
        ]
    },

    # ── Page 3: More Products, Pricing, Security ─────────────────────────────
    {
        "sections": [
            {
                "heading": "4. SparkGovernance — Data Catalog & Lineage",
                "body": (
                    "SparkGovernance gives data teams a single pane of glass over all their "
                    "data assets: tables, dashboards, ML models, and pipelines.\n\n"
                    "Key features:\n"
                    "  • Automated metadata harvesting via passive query log analysis.\n"
                    "  • Column-level lineage graph rendered as an interactive DAG.\n"
                    "  • Business glossary with ownership and certification workflows.\n"
                    "  • PII classification and GDPR / CCPA compliance reporting.\n"
                    "  • Integration with Jira and Slack for data-quality incident routing."
                ),
            },
            {
                "heading": "5. SparkAlert — Anomaly Detection & Observability",
                "body": (
                    "SparkAlert monitors data pipelines and warehouse queries for anomalies, "
                    "SLA breaches, and cost spikes, alerting the right person before downstream "
                    "consumers notice a problem.\n\n"
                    "Key features:\n"
                    "  • ML-based anomaly detection with zero manual threshold-setting.\n"
                    "  • Freshness, volume, schema, and distribution monitors out of the box.\n"
                    "  • PagerDuty, OpsGenie, Slack, and email integrations.\n"
                    "  • Cost anomaly detection: flags when a query or pipeline exceeds budget.\n"
                    "  • Root-cause analysis assistant powered by LLM."
                ),
            },
            {
                "heading": "Pricing Tiers",
                "body": (
                    "All plans are billed annually. Monthly billing is available at a 15% "
                    "premium. All prices are per product unless the Platform bundle is chosen.\n\n"
                    "Starter — $499 / month\n"
                    "  • Up to 5 users.\n"
                    "  • 50 GB storage (SparkDB) or 10 M events/month (SparkStream).\n"
                    "  • Community support (forum + docs).\n"
                    "  • 99.9% uptime SLA.\n"
                    "  • Best for: small teams evaluating NovaSpark in production.\n\n"
                    "Professional — $1,999 / month\n"
                    "  • Up to 25 users.\n"
                    "  • 500 GB storage or 200 M events/month.\n"
                    "  • Email and chat support (business hours, 4-hour response SLA).\n"
                    "  • 99.95% uptime SLA.\n"
                    "  • SSO (SAML 2.0, OIDC).\n"
                    "  • Best for: growing data teams with production workloads.\n\n"
                    "Enterprise — Custom pricing\n"
                    "  • Unlimited users.\n"
                    "  • Custom storage and event-volume commitments.\n"
                    "  • 24/7 dedicated support with a named Customer Success Manager.\n"
                    "  • 99.99% uptime SLA with financial penalties for breaches.\n"
                    "  • Private networking (VPC peering, PrivateLink).\n"
                    "  • Custom data retention up to 10 years.\n"
                    "  • HIPAA BAA, SOC 2 Type II, ISO 27001 compliance packages available.\n"
                    "  • On-premise / hybrid deployment option.\n"
                    "  • Best for: large enterprises with compliance, scale, or custom needs.\n\n"
                    "Platform Bundle — 30% discount\n"
                    "  • All five products at the same tier for 30% off the sum of individual "
                    "list prices. Ideal for teams adopting the full NovaSpark ecosystem."
                ),
            },
        ]
    },

    # ── Page 4: Security, Support, FAQs ─────────────────────────────────────
    {
        "sections": [
            {
                "heading": "Security & Compliance",
                "body": (
                    "Security is a first-class concern at NovaSpark. We invest heavily in "
                    "infrastructure hardening, third-party audits, and customer-controlled "
                    "encryption.\n\n"
                    "Certifications & standards:\n"
                    "  • SOC 2 Type II (annual audit, report available on request).\n"
                    "  • ISO 27001 certified since 2022.\n"
                    "  • GDPR and CCPA compliant. DPA available on the Enterprise plan.\n"
                    "  • HIPAA Business Associate Agreement available for Enterprise customers.\n\n"
                    "Encryption:\n"
                    "  • All data encrypted at rest with AES-256.\n"
                    "  • All data in transit encrypted with TLS 1.3.\n"
                    "  • Customer-managed encryption keys (CMEK) available on Enterprise.\n"
                    "  • Key rotation on a configurable schedule (default: 90 days).\n\n"
                    "Access control:\n"
                    "  • Role-based access control (RBAC) with 12 built-in roles.\n"
                    "  • Attribute-based access control (ABAC) on Enterprise.\n"
                    "  • Multi-factor authentication enforced for all accounts.\n"
                    "  • SSO via SAML 2.0 and OIDC on Professional and Enterprise plans.\n"
                    "  • Audit logs retained for 12 months (36 months on Enterprise).\n\n"
                    "Network security:\n"
                    "  • IP allowlisting available on all paid plans.\n"
                    "  • VPC peering and AWS PrivateLink on Enterprise.\n"
                    "  • Quarterly penetration tests by independent security firms.\n"
                    "  • Bug bounty programme managed via HackerOne."
                ),
            },
            {
                "heading": "Support & Contact Information",
                "body": (
                    "Support channels (vary by plan):\n"
                    "  • Documentation portal: docs.novaspark.io\n"
                    "  • Community forum: community.novaspark.io\n"
                    "  • In-app chat (Professional & Enterprise): business hours, "
                    "4-hour first response.\n"
                    "  • Email: support@novaspark.io\n"
                    "  • Dedicated phone line (Enterprise only): +1-800-NOVA-SPK\n"
                    "  • Slack Connect channel (Enterprise only): direct line to your CSM.\n\n"
                    "Sales enquiries:\n"
                    "  • Email: sales@novaspark.io\n"
                    "  • Book a demo: novaspark.io/demo\n"
                    "  • Partner programme: partners@novaspark.io\n\n"
                    "Headquarters:\n"
                    "  NovaSpark Technologies Inc.\n"
                    "  500 Congress Ave, Suite 2200\n"
                    "  Austin, TX 78701, United States"
                ),
            },
            {
                "heading": "Frequently Asked Questions",
                "body": (
                    "Q: Can I try NovaSpark before purchasing?\n"
                    "A: Yes. Every product offers a 14-day free trial with full functionality "
                    "and no credit card required. Trials can be extended to 30 days on request.\n\n"
                    "Q: Do you support on-premise deployment?\n"
                    "A: On-premise and hybrid (cloud + on-prem) deployments are available "
                    "exclusively on the Enterprise plan. We provide a Kubernetes Helm chart "
                    "and dedicated implementation support.\n\n"
                    "Q: How is data billed in SparkDB?\n"
                    "A: Storage is billed per GB-month of compressed data. Compute is billed "
                    "per vCPU-hour consumed by active query clusters. Paused clusters incur "
                    "zero compute costs.\n\n"
                    "Q: What happens if I exceed my event quota in SparkStream?\n"
                    "A: Events over the monthly quota are metered at $0.12 per million additional "
                    "events. You receive an email alert at 80% and 100% of your quota.\n\n"
                    "Q: Is there a Service Level Agreement for uptime?\n"
                    "A: Yes. Starter: 99.9% (allows ~8.7 h downtime/year). Professional: 99.95% "
                    "(~4.4 h). Enterprise: 99.99% (~52 min). Enterprise customers receive "
                    "automatic service credits for any breach.\n\n"
                    "Q: Can I export my data if I cancel?\n"
                    "A: Absolutely. You can export all data in open formats (Parquet, CSV, JSON) "
                    "at any time. After cancellation we retain your data for 30 days before "
                    "permanent deletion, giving you time to complete the export."
                ),
            },
        ]
    },
]


def _ascii(text: str) -> str:
    """Replace non-latin-1 characters so fpdf2's built-in fonts work."""
    return (
        text.replace("—", "-")   # em-dash
            .replace("–", "-")   # en-dash
            .replace("‘", "'")   # left single quote
            .replace("’", "'")   # right single quote
            .replace("“", '"')   # left double quote
            .replace("”", '"')   # right double quote
            .replace("•", "*")   # bullet
            .replace("…", "...") # ellipsis
    )


def build_pdf(output_path: str) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)

    for page_data in PAGES:
        pdf.add_page()
        for section in page_data["sections"]:
            heading = _ascii(section["heading"])
            body = _ascii(section["body"])

            # Section heading
            pdf.set_font("Helvetica", style="B", size=12)
            pdf.set_fill_color(230, 240, 255)
            pdf.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT", fill=True)
            pdf.ln(1)

            # Body text
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(0, 5.5, body)
            pdf.ln(4)

    pdf.output(output_path)
    print(f"[create_pdf] Written: {output_path}  ({Path(output_path).stat().st_size:,} bytes)")


if __name__ == "__main__":
    out = Path(__file__).parent.parent / "resources" / "company_knowledge.pdf"
    out.parent.mkdir(exist_ok=True)
    build_pdf(str(out))
