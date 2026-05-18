"""Tech Stack Detector Tool.

Detects technologies used by a company through multiple methods:
web headers, job descriptions, and public data sources.
"""
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

# Known technology signatures in job descriptions and web content
TECH_SIGNATURES = {
    # Cloud Providers
    "AWS": ["aws", "amazon web services", "ec2", "s3", "lambda", "redshift", "sagemaker"],
    "Azure": ["azure", "microsoft azure", "azure devops", "azure data factory"],
    "GCP": ["google cloud", "gcp", "bigquery", "cloud run", "vertex ai"],
    # Databases
    "PostgreSQL": ["postgresql", "postgres", "psql"],
    "MySQL": ["mysql", "mariadb"],
    "MongoDB": ["mongodb", "mongo"],
    "Snowflake": ["snowflake"],
    "Databricks": ["databricks", "delta lake"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch", "elastic", "opensearch"],
    # Data & Analytics
    "dbt": ["dbt", "data build tool"],
    "Airflow": ["airflow", "apache airflow"],
    "Spark": ["spark", "pyspark", "apache spark"],
    "Kafka": ["kafka", "apache kafka", "confluent"],
    "Tableau": ["tableau"],
    "Looker": ["looker"],
    "Power BI": ["power bi", "powerbi"],
    # CRM & Business
    "Salesforce": ["salesforce", "sfdc", "sales cloud"],
    "HubSpot": ["hubspot"],
    "Marketo": ["marketo"],
    # DevOps & Infrastructure
    "Docker": ["docker", "container"],
    "Kubernetes": ["kubernetes", "k8s", "eks", "aks", "gke"],
    "Terraform": ["terraform", "infrastructure as code"],
    "Jenkins": ["jenkins"],
    "GitHub": ["github", "github actions"],
    "GitLab": ["gitlab"],
    # Languages & Frameworks
    "Python": ["python", "django", "flask", "fastapi"],
    "Java": ["java", "spring boot", "spring framework"],
    "JavaScript": ["javascript", "typescript", "node.js", "react", "angular", "vue"],
    "Go": ["golang", " go ", "go programming"],
    "Rust": ["rust programming", "rustlang"],
}


def tech_stack_detector(
    domain: str,
    company_name: str = "",
    check_methods: list[str] | None = None,
) -> dict:
    """Detect technologies used by a company.

    Args:
        domain: Company domain to analyze
        company_name: Company name for search queries
        check_methods: Methods to use — ["web_headers", "job_descriptions", "web_content"]

    Returns dict with detected_technologies, migrations, confidence scores.
    """
    check_methods = check_methods or ["web_content", "job_descriptions"]
    detected: dict[str, dict] = {}  # tech_name -> {sources: [], confidence: float}

    # Method 1: Web content analysis
    if "web_content" in check_methods and domain:
        try:
            from app.tools.web_scraper_tool import scrape_webpage
            raw = scrape_webpage(url=f"https://{domain}")
            if isinstance(raw, dict):
                text = (raw.get("text", "") or "").lower()
                tech_signals = raw.get("tech_signals", [])

                # From scraper's built-in tech detection
                for tech in tech_signals:
                    if tech not in detected:
                        detected[tech] = {"sources": [], "confidence": 0.6}
                    detected[tech]["sources"].append("web_scraper")

                # From content matching
                for tech_name, keywords in TECH_SIGNATURES.items():
                    if any(kw in text for kw in keywords):
                        if tech_name not in detected:
                            detected[tech_name] = {"sources": [], "confidence": 0.4}
                        detected[tech_name]["sources"].append("web_content")
                        detected[tech_name]["confidence"] = min(1.0, detected[tech_name]["confidence"] + 0.2)
        except Exception as e:
            logger.warning(f"Web content tech detection failed for {domain}: {e}")

    # Method 2: Job description analysis
    if "job_descriptions" in check_methods and (company_name or domain):
        search_name = company_name or domain.split(".")[0]
        try:
            articles, source = asyncio.run(_search_tech_jobs(search_name))
            combined_text = ""
            for article in articles[:10]:
                combined_text += " " + (article.get("title", "") + " " + article.get("body", "")).lower()

            for tech_name, keywords in TECH_SIGNATURES.items():
                matches = sum(1 for kw in keywords if kw in combined_text)
                if matches > 0:
                    if tech_name not in detected:
                        detected[tech_name] = {"sources": [], "confidence": 0.0}
                    detected[tech_name]["sources"].append("job_descriptions")
                    # More keyword matches = higher confidence
                    boost = min(0.4, matches * 0.15)
                    detected[tech_name]["confidence"] = min(1.0, detected[tech_name]["confidence"] + 0.5 + boost)
        except Exception as e:
            logger.warning(f"Job-based tech detection failed for {search_name}: {e}")

    # Build result
    technologies = []
    for tech_name, info in sorted(detected.items(), key=lambda x: -x[1]["confidence"]):
        conf = info["confidence"]
        confidence_label = "high" if conf >= 0.7 else "medium" if conf >= 0.4 else "low"
        technologies.append({
            "name": tech_name,
            "category": _categorize_tech(tech_name),
            "confidence": confidence_label,
            "confidence_score": round(conf, 2),
            "evidence_sources": list(set(info["sources"])),
        })

    # Detect possible migrations
    migrations = _detect_migrations(technologies)

    return {
        "domain": domain,
        "company_name": company_name,
        "detected_technologies": technologies[:30],
        "total_detected": len(technologies),
        "migrations": migrations,
        "methods_used": check_methods,
    }


def _categorize_tech(name: str) -> str:
    categories = {
        "Cloud": ["AWS", "Azure", "GCP"],
        "Database": ["PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch"],
        "Data Warehouse": ["Snowflake", "Databricks"],
        "Data Pipeline": ["dbt", "Airflow", "Spark", "Kafka"],
        "BI & Analytics": ["Tableau", "Looker", "Power BI"],
        "CRM": ["Salesforce", "HubSpot"],
        "Marketing": ["Marketo"],
        "DevOps": ["Docker", "Kubernetes", "Terraform", "Jenkins"],
        "Version Control": ["GitHub", "GitLab"],
        "Language": ["Python", "Java", "JavaScript", "Go", "Rust"],
    }
    for category, techs in categories.items():
        if name in techs:
            return category
    return "Other"


def _detect_migrations(technologies: list[dict]) -> list[dict]:
    """Detect possible technology migrations from competing tools."""
    migration_pairs = [
        ("Hadoop", "Snowflake"), ("Hadoop", "Databricks"),
        ("Tableau", "Looker"), ("Tableau", "Power BI"),
        ("Jenkins", "GitHub"), ("Jenkins", "GitLab"),
        ("MySQL", "PostgreSQL"),
    ]
    tech_names = {t["name"] for t in technologies}
    migrations = []
    for old, new in migration_pairs:
        if new in tech_names and old in tech_names:
            migrations.append({
                "from": old,
                "to": new,
                "confidence": "medium",
                "evidence": f"Both {old} and {new} detected — possible migration",
            })
    return migrations


async def _search_tech_jobs(company_name: str):
    from app.services.search_helpers import resilient_search
    return await resilient_search(
        query=f'"{company_name}" software engineer OR developer OR data engineer',
        max_results=10,
        company_name=company_name,
    )
