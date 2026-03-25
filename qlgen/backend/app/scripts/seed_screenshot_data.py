"""Seed realistic data for Playwright screenshot capture.

Usage:
    cd backend && ../backend/venv/bin/python -m app.scripts.seed_screenshot_data

Populates: users, ICP configs, pipeline runs, companies, contacts,
           company stage results, tool registry, audit logs.
"""
import asyncio
import sys
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure backend dir is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
load_dotenv(env_path)
env_path2 = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path2)

from sqlalchemy import select, delete
from app.db.session import async_session
from app.models.user import User
from app.models.icp import ICPConfig
from app.models.pipeline import PipelineRun
from app.models.company import Company
from app.models.contact import Contact
from app.models.company_stage import CompanyStageResult
from app.models.tool_registry import ToolRegistry
from app.models.audit_log import AuditLog
from app.models.discovery_intelligence import ToolEffectiveness

# ---------------------------------------------------------------------------
# Marker domain — all seeded users use this so cleanup is easy
# ---------------------------------------------------------------------------
SEED_DOMAIN = "gadgeon.com"
SEED_EMAILS = [
    "test@gadgeon.com",
    "admin@gadgeon.com",
    "sarah.patel@gadgeon.com",
    "james.chen@gadgeon.com",
    "priya.nair@gadgeon.com",
    "david.wilson@gadgeon.com",
]

NOW = datetime.now(timezone.utc)


def _ago(**kw):
    return NOW - timedelta(**kw)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def build_users():
    return [
        User(id=uuid.uuid4(), email="test@gadgeon.com", name="Sreejith K", role="super_admin",
             is_active=True, last_login_at=_ago(hours=1), picture_url=None, google_id="seed_1"),
        User(id=uuid.uuid4(), email="admin@gadgeon.com", name="Ravi Kumar", role="admin",
             is_active=True, last_login_at=_ago(hours=5), picture_url=None, google_id="seed_2"),
        User(id=uuid.uuid4(), email="sarah.patel@gadgeon.com", name="Sarah Patel", role="user",
             is_active=True, last_login_at=_ago(days=1), picture_url=None, google_id="seed_3"),
        User(id=uuid.uuid4(), email="james.chen@gadgeon.com", name="James Chen", role="user",
             is_active=True, last_login_at=_ago(days=2), picture_url=None, google_id="seed_4"),
        User(id=uuid.uuid4(), email="priya.nair@gadgeon.com", name="Priya Nair", role="user",
             is_active=True, last_login_at=_ago(days=7), picture_url=None, google_id="seed_5"),
        User(id=uuid.uuid4(), email="david.wilson@gadgeon.com", name="David Wilson", role="user",
             is_active=False, last_login_at=_ago(days=30), picture_url=None, google_id="seed_6"),
    ]


# ---------------------------------------------------------------------------
# ICP Configs
# ---------------------------------------------------------------------------
ICP_CONFIGS_DATA = [
    {
        "name": "US Enterprise SaaS",
        "description": "Enterprise SaaS companies in the United States with 200+ employees focused on cloud infrastructure modernization",
        "config_json": {
            "firmographic_details": {
                "industry_types": [
                    {"vertical": "Software & Technology", "sub_vertical": "Enterprise SaaS"},
                    {"vertical": "Cloud Computing", "sub_vertical": "Infrastructure"},
                ],
                "geography": {"countries": ["United States"]},
                "revenue_range": {"min": 50000000, "max": 2000000000, "currency": "USD"},
                "employee_range": {"min": 200, "max": 10000},
                "low_cost_center": False,
            },
            "target_capability": {
                "offerings": [
                    "Cloud infrastructure modernization",
                    "Platform engineering",
                    "DevOps transformation",
                    "Kubernetes migration",
                ],
                "condition": "OR",
            },
            "urgency_signals": {
                "signals": [
                    "Recent Series C or later funding round",
                    "Cloud migration initiative announced",
                    "New CTO or VP Engineering hired in last 6 months",
                    "IPO preparation or recent IPO",
                ],
                "condition": "OR",
            },
            "budget_signals": {
                "signals": [
                    "Annual IT budget exceeds $5M",
                    "Recent fundraise over $50M",
                    "Expanding engineering team aggressively",
                ],
                "condition": "OR",
            },
            "authority_roles": {
                "target_roles": ["CTO", "VP of Engineering", "Head of Platform", "Director of Infrastructure"],
            },
        },
    },
    {
        "name": "European FinTech",
        "description": "FinTech companies across the EU and UK seeking digital transformation and regulatory compliance solutions",
        "config_json": {
            "firmographic_details": {
                "industry_types": [
                    {"vertical": "Financial Services", "sub_vertical": "FinTech"},
                    {"vertical": "Financial Services", "sub_vertical": "Digital Banking"},
                ],
                "geography": {"countries": ["United Kingdom", "Germany", "France", "Netherlands"]},
                "revenue_range": {"min": 10000000, "max": 500000000, "currency": "EUR"},
                "employee_range": {"min": 50, "max": 2000},
                "low_cost_center": False,
            },
            "target_capability": {
                "offerings": [
                    "Regulatory compliance automation",
                    "Open banking API development",
                    "Payment processing modernization",
                ],
                "condition": "OR",
            },
            "urgency_signals": {
                "signals": [
                    "PSD3 regulatory deadline approaching",
                    "Digital banking license obtained",
                    "Partnership with major bank announced",
                ],
                "condition": "OR",
            },
            "budget_signals": {
                "signals": [
                    "Series B+ funding in last 12 months",
                    "Compliance budget increase",
                    "Technology transformation budget allocated",
                ],
                "condition": "OR",
            },
            "authority_roles": {
                "target_roles": ["CTO", "Chief Compliance Officer", "Head of Engineering", "VP Product"],
            },
        },
    },
    {
        "name": "APAC Healthcare Tech",
        "description": "Healthcare technology companies in Asia-Pacific focused on digital health platforms and telemedicine",
        "config_json": {
            "firmographic_details": {
                "industry_types": [
                    {"vertical": "Healthcare", "sub_vertical": "HealthTech"},
                    {"vertical": "Healthcare", "sub_vertical": "Telemedicine"},
                ],
                "geography": {"countries": ["India", "Singapore", "Australia", "Japan"]},
                "revenue_range": {"min": 5000000, "max": 200000000, "currency": "USD"},
                "employee_range": {"min": 30, "max": 1000},
                "low_cost_center": True,
            },
            "target_capability": {
                "offerings": [
                    "Telemedicine platform development",
                    "EHR/EMR system integration",
                    "Healthcare data analytics",
                ],
                "condition": "OR",
            },
            "urgency_signals": {
                "signals": [
                    "Government digital health mandate",
                    "Rapid user growth post-COVID",
                    "Hospital chain partnership signed",
                ],
                "condition": "OR",
            },
            "budget_signals": {
                "signals": [
                    "Recent venture funding",
                    "Government grant received",
                    "Revenue growing >30% YoY",
                ],
                "condition": "OR",
            },
            "authority_roles": {
                "target_roles": ["CTO", "VP of Product", "Head of Digital Health", "Chief Medical Information Officer"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Companies — realistic names, varied scores
# ---------------------------------------------------------------------------
COMPANIES_DATA = [
    # --- Run 1 (US Enterprise SaaS — completed) ~25 companies ---
    {"name": "Meridian Software", "industry": "Enterprise SaaS", "country": "United States", "city": "San Francisco", "state_region": "California", "website": "https://meridiansoftware.com", "employee_count": 850, "revenue_estimate": 180000000, "icp_match_score": 92, "budget_signal_score": 88, "urgency_signal_score": 85, "final_score": 91, "deal_hotness_score": 94, "deal_hotness_tier": "A", "qualification": "qualified", "description": "Cloud-native enterprise platform for workflow automation and data orchestration."},
    {"name": "NovaBridge Analytics", "industry": "Data Analytics", "country": "United States", "city": "Austin", "state_region": "Texas", "website": "https://novabridge.io", "employee_count": 420, "revenue_estimate": 75000000, "icp_match_score": 88, "budget_signal_score": 82, "urgency_signal_score": 79, "final_score": 85, "deal_hotness_score": 87, "deal_hotness_tier": "A", "qualification": "qualified", "description": "AI-powered analytics platform helping enterprises transform raw data into actionable insights."},
    {"name": "Stratosphere Cloud", "industry": "Cloud Computing", "country": "United States", "city": "Seattle", "state_region": "Washington", "website": "https://stratospherecloud.com", "employee_count": 1200, "revenue_estimate": 350000000, "icp_match_score": 95, "budget_signal_score": 91, "urgency_signal_score": 88, "final_score": 93, "deal_hotness_score": 96, "deal_hotness_tier": "A", "qualification": "qualified", "description": "Multi-cloud infrastructure management platform for Fortune 500 enterprises."},
    {"name": "Codestream Labs", "industry": "Developer Tools", "country": "United States", "city": "Denver", "state_region": "Colorado", "website": "https://codestreamlabs.com", "employee_count": 310, "revenue_estimate": 52000000, "icp_match_score": 78, "budget_signal_score": 72, "urgency_signal_score": 68, "final_score": 74, "deal_hotness_score": 71, "deal_hotness_tier": "B", "qualification": "qualified", "description": "Integrated developer platform with CI/CD, code review, and deployment automation."},
    {"name": "Luminos Health Systems", "industry": "HealthTech", "country": "United States", "city": "Boston", "state_region": "Massachusetts", "website": "https://luminoshealth.com", "employee_count": 560, "revenue_estimate": 95000000, "icp_match_score": 65, "budget_signal_score": 60, "urgency_signal_score": 55, "final_score": 60, "deal_hotness_score": 58, "deal_hotness_tier": "C", "qualification": "qualified", "description": "Healthcare workflow optimization and patient data management platform."},
    {"name": "Apex Workflow", "industry": "Enterprise SaaS", "country": "United States", "city": "Chicago", "state_region": "Illinois", "website": "https://apexworkflow.com", "employee_count": 680, "revenue_estimate": 120000000, "icp_match_score": 85, "budget_signal_score": 80, "urgency_signal_score": 77, "final_score": 82, "deal_hotness_score": 84, "deal_hotness_tier": "A", "qualification": "qualified", "description": "Enterprise process automation and workflow management for large organizations."},
    {"name": "Veridian Security", "industry": "Cybersecurity", "country": "United States", "city": "Reston", "state_region": "Virginia", "website": "https://veridiansec.com", "employee_count": 390, "revenue_estimate": 67000000, "icp_match_score": 72, "budget_signal_score": 69, "urgency_signal_score": 75, "final_score": 72, "deal_hotness_score": 73, "deal_hotness_tier": "B", "qualification": "qualified", "description": "Zero-trust security platform for cloud-native enterprise environments."},
    {"name": "DataPulse Inc.", "industry": "Data Infrastructure", "country": "United States", "city": "New York", "state_region": "New York", "website": "https://datapulse.io", "employee_count": 510, "revenue_estimate": 88000000, "icp_match_score": 82, "budget_signal_score": 78, "urgency_signal_score": 81, "final_score": 80, "deal_hotness_score": 82, "deal_hotness_tier": "A", "qualification": "qualified", "description": "Real-time data pipeline and streaming analytics infrastructure."},
    {"name": "CloudForge Systems", "industry": "Cloud Computing", "country": "United States", "city": "Portland", "state_region": "Oregon", "website": "https://cloudforge.io", "employee_count": 275, "revenue_estimate": 45000000, "icp_match_score": 76, "budget_signal_score": 70, "urgency_signal_score": 65, "final_score": 71, "deal_hotness_score": 68, "deal_hotness_tier": "B", "qualification": "qualified", "description": "Infrastructure-as-code platform for automated cloud deployments."},
    {"name": "Synthetica AI", "industry": "Artificial Intelligence", "country": "United States", "city": "Palo Alto", "state_region": "California", "website": "https://synthetica.ai", "employee_count": 940, "revenue_estimate": 210000000, "icp_match_score": 90, "budget_signal_score": 86, "urgency_signal_score": 83, "final_score": 88, "deal_hotness_score": 90, "deal_hotness_tier": "A", "qualification": "qualified", "description": "Enterprise AI platform for automated decision-making and predictive analytics."},
    {"name": "PivotStack", "industry": "Enterprise SaaS", "country": "United States", "city": "Salt Lake City", "state_region": "Utah", "website": "https://pivotstack.com", "employee_count": 220, "revenue_estimate": 38000000, "icp_match_score": 68, "budget_signal_score": 62, "urgency_signal_score": 58, "final_score": 63, "deal_hotness_score": 60, "deal_hotness_tier": "C", "qualification": "qualified", "description": "Modular integration platform connecting enterprise SaaS applications."},
    {"name": "TerraScale Networks", "industry": "Networking", "country": "United States", "city": "San Jose", "state_region": "California", "website": "https://terrascale.net", "employee_count": 780, "revenue_estimate": 145000000, "icp_match_score": 81, "budget_signal_score": 76, "urgency_signal_score": 73, "final_score": 78, "deal_hotness_score": 79, "deal_hotness_tier": "B", "qualification": "qualified", "description": "Software-defined networking solutions for hybrid cloud environments."},
    {"name": "Quantum Leap SaaS", "industry": "Enterprise SaaS", "country": "United States", "city": "Atlanta", "state_region": "Georgia", "website": "https://quantumleap.saas", "employee_count": 450, "revenue_estimate": 82000000, "icp_match_score": 74, "budget_signal_score": 68, "urgency_signal_score": 71, "final_score": 71, "deal_hotness_score": 70, "deal_hotness_tier": "B", "qualification": "qualified", "description": "Subscription management and revenue optimization platform."},
    {"name": "Gridline Infra", "industry": "Cloud Infrastructure", "country": "United States", "city": "Phoenix", "state_region": "Arizona", "website": "https://gridlineinfra.com", "employee_count": 340, "revenue_estimate": 58000000, "icp_match_score": 70, "budget_signal_score": 64, "urgency_signal_score": 60, "final_score": 65, "deal_hotness_score": 63, "deal_hotness_tier": "C", "qualification": "qualified", "description": "Edge computing infrastructure for distributed enterprise applications."},
    {"name": "Nebula DevOps", "industry": "Developer Tools", "country": "United States", "city": "Raleigh", "state_region": "North Carolina", "website": "https://nebuladevops.com", "employee_count": 190, "revenue_estimate": 32000000, "icp_match_score": 60, "budget_signal_score": 55, "urgency_signal_score": 50, "final_score": 55, "deal_hotness_score": 52, "deal_hotness_tier": "C", "qualification": "qualified", "description": "Continuous delivery and deployment automation platform for development teams."},
    # --- Run 2 (European FinTech — completed) ~20 companies ---
    {"name": "FinEdge Technologies", "industry": "FinTech", "country": "United Kingdom", "city": "London", "state_region": "England", "website": "https://finedge.co.uk", "employee_count": 380, "revenue_estimate": 65000000, "icp_match_score": 91, "budget_signal_score": 87, "urgency_signal_score": 84, "final_score": 89, "deal_hotness_score": 92, "deal_hotness_tier": "A", "qualification": "qualified", "description": "Open banking API platform enabling seamless financial data sharing."},
    {"name": "PayStream Europe", "industry": "Payments", "country": "Netherlands", "city": "Amsterdam", "state_region": "North Holland", "website": "https://paystream.eu", "employee_count": 290, "revenue_estimate": 48000000, "icp_match_score": 86, "budget_signal_score": 82, "urgency_signal_score": 80, "final_score": 84, "deal_hotness_score": 85, "deal_hotness_tier": "A", "qualification": "qualified", "description": "Cross-border payment processing with real-time settlement."},
    {"name": "Complytics GmbH", "industry": "RegTech", "country": "Germany", "city": "Frankfurt", "state_region": "Hesse", "website": "https://complytics.de", "employee_count": 210, "revenue_estimate": 35000000, "icp_match_score": 84, "budget_signal_score": 79, "urgency_signal_score": 82, "final_score": 82, "deal_hotness_score": 83, "deal_hotness_tier": "A", "qualification": "qualified", "description": "Automated regulatory compliance and reporting for financial institutions."},
    {"name": "LedgerVault", "industry": "FinTech", "country": "United Kingdom", "city": "Edinburgh", "state_region": "Scotland", "website": "https://ledgervault.io", "employee_count": 160, "revenue_estimate": 28000000, "icp_match_score": 79, "budget_signal_score": 74, "urgency_signal_score": 71, "final_score": 76, "deal_hotness_score": 75, "deal_hotness_tier": "B", "qualification": "qualified", "description": "Digital asset custody and blockchain-based settlement infrastructure."},
    {"name": "NeoBank France", "industry": "Digital Banking", "country": "France", "city": "Paris", "state_region": "Ile-de-France", "website": "https://neobankfr.com", "employee_count": 520, "revenue_estimate": 92000000, "icp_match_score": 88, "budget_signal_score": 84, "urgency_signal_score": 86, "final_score": 86, "deal_hotness_score": 88, "deal_hotness_tier": "A", "qualification": "qualified", "description": "Digital-first banking platform serving SMBs across the eurozone."},
    {"name": "WealthTech NL", "industry": "WealthTech", "country": "Netherlands", "city": "Rotterdam", "state_region": "South Holland", "website": "https://wealthtechnl.com", "employee_count": 140, "revenue_estimate": 22000000, "icp_match_score": 72, "budget_signal_score": 67, "urgency_signal_score": 63, "final_score": 68, "deal_hotness_score": 66, "deal_hotness_tier": "B", "qualification": "qualified", "description": "AI-driven wealth management and robo-advisory platform."},
    {"name": "InsurTech Berlin", "industry": "InsurTech", "country": "Germany", "city": "Berlin", "state_region": "Berlin", "website": "https://insurtechberlin.de", "employee_count": 310, "revenue_estimate": 55000000, "icp_match_score": 76, "budget_signal_score": 72, "urgency_signal_score": 69, "final_score": 73, "deal_hotness_score": 72, "deal_hotness_tier": "B", "qualification": "qualified", "description": "Digital insurance distribution and claims automation."},
    {"name": "CreditPulse UK", "industry": "FinTech", "country": "United Kingdom", "city": "Manchester", "state_region": "England", "website": "https://creditpulse.co.uk", "employee_count": 180, "revenue_estimate": 30000000, "icp_match_score": 70, "budget_signal_score": 65, "urgency_signal_score": 62, "final_score": 66, "deal_hotness_score": 64, "deal_hotness_tier": "B", "qualification": "qualified", "description": "Real-time credit scoring and risk assessment for lenders."},
    {"name": "TradeFlex", "industry": "Trading", "country": "United Kingdom", "city": "London", "state_region": "England", "website": "https://tradeflex.io", "employee_count": 250, "revenue_estimate": 42000000, "icp_match_score": 66, "budget_signal_score": 61, "urgency_signal_score": 58, "final_score": 62, "deal_hotness_score": 60, "deal_hotness_tier": "C", "qualification": "qualified", "description": "Algorithmic trading platform for institutional investors."},
    {"name": "PayNova", "industry": "Payments", "country": "France", "city": "Lyon", "state_region": "Auvergne-Rhone-Alpes", "website": "https://paynova.fr", "employee_count": 120, "revenue_estimate": 18000000, "icp_match_score": 62, "budget_signal_score": 57, "urgency_signal_score": 54, "final_score": 58, "deal_hotness_score": 55, "deal_hotness_tier": "C", "qualification": "qualified", "description": "Mobile payment solutions for European merchants."},
    # --- Run 3 (APAC Healthcare — running, partial data) ~8 companies ---
    {"name": "MedConnect India", "industry": "HealthTech", "country": "India", "city": "Bangalore", "state_region": "Karnataka", "website": "https://medconnect.in", "employee_count": 420, "revenue_estimate": 35000000, "icp_match_score": 89, "budget_signal_score": 84, "urgency_signal_score": 81, "final_score": 86, "deal_hotness_score": 88, "deal_hotness_tier": "A", "qualification": "qualified", "description": "Telemedicine and digital health platform connecting rural patients with specialists."},
    {"name": "HealthBridge SG", "industry": "HealthTech", "country": "Singapore", "city": "Singapore", "state_region": "Central", "website": "https://healthbridge.sg", "employee_count": 280, "revenue_estimate": 45000000, "icp_match_score": 85, "budget_signal_score": 80, "urgency_signal_score": 78, "final_score": 82, "deal_hotness_score": 83, "deal_hotness_tier": "A", "qualification": "qualified", "description": "Healthcare data interoperability platform for Southeast Asian hospitals."},
    {"name": "CareOS Australia", "industry": "HealthTech", "country": "Australia", "city": "Sydney", "state_region": "New South Wales", "website": "https://careos.com.au", "employee_count": 190, "revenue_estimate": 28000000, "icp_match_score": 78, "budget_signal_score": 73, "urgency_signal_score": 70, "final_score": 74, "deal_hotness_score": 72, "deal_hotness_tier": "B", "qualification": "qualified", "description": "Patient engagement and care coordination platform for Australian healthcare."},
    {"name": "PharmaTech JP", "industry": "PharmaTech", "country": "Japan", "city": "Tokyo", "state_region": "Kanto", "website": "https://pharmatech.jp", "employee_count": 350, "revenue_estimate": 60000000, "icp_match_score": 74, "budget_signal_score": 69, "urgency_signal_score": 66, "final_score": 70, "deal_hotness_score": 68, "deal_hotness_tier": "B", "qualification": "qualified", "description": "Digital clinical trial management and pharmaceutical logistics platform."},
    {"name": "TeleHealth India", "industry": "Telemedicine", "country": "India", "city": "Mumbai", "state_region": "Maharashtra", "website": "https://telehealth.in", "employee_count": 560, "revenue_estimate": 48000000, "icp_match_score": 82, "budget_signal_score": 77, "urgency_signal_score": 75, "final_score": 79, "deal_hotness_score": 80, "deal_hotness_tier": "A", "qualification": "qualified", "description": "Comprehensive telemedicine platform serving 50M+ patients across India."},
]

# Contacts — 2-3 per company
CONTACT_TEMPLATES = [
    # (full_name, first, last, designation, role_category, email_local, phone, linkedin_suffix, confidence)
    ("Michael Torres", "Michael", "Torres", "Chief Technology Officer", "C-Suite", "michael.torres", "+1-415-555-0101", "michaeltorres", 0.95),
    ("Rachel Kim", "Rachel", "Kim", "VP of Engineering", "VP", "rachel.kim", "+1-415-555-0102", "rachelkim", 0.92),
    ("David Nakamura", "David", "Nakamura", "Director of Infrastructure", "Director", "david.nakamura", "+1-415-555-0103", "davidnakamura", 0.88),
    ("Emma Richardson", "Emma", "Richardson", "Head of Platform Engineering", "Head", "emma.richardson", "+1-512-555-0201", "emmarichardson", 0.90),
    ("Carlos Mendez", "Carlos", "Mendez", "VP of Product", "VP", "carlos.mendez", "+1-512-555-0202", "carlosmendez", 0.87),
    ("Sarah Blackwell", "Sarah", "Blackwell", "CTO", "C-Suite", "sarah.blackwell", "+1-206-555-0301", "sarahblackwell", 0.94),
    ("James O'Brien", "James", "O'Brien", "Director of DevOps", "Director", "james.obrien", "+1-206-555-0302", "jamesobrien", 0.86),
    ("Aisha Patel", "Aisha", "Patel", "VP of Cloud Architecture", "VP", "aisha.patel", "+1-303-555-0401", "aishapatel", 0.91),
    ("Tom Foster", "Tom", "Foster", "Head of Engineering", "Head", "tom.foster", "+1-617-555-0501", "tomfoster", 0.89),
    ("Lisa Chang", "Lisa", "Chang", "Chief Information Officer", "C-Suite", "lisa.chang", "+1-312-555-0601", "lisachang", 0.93),
    ("Robert Mueller", "Robert", "Mueller", "Director of Security", "Director", "robert.mueller", "+1-703-555-0701", "robertmueller", 0.85),
    ("Jennifer Watts", "Jennifer", "Watts", "VP of Data Engineering", "VP", "jennifer.watts", "+1-212-555-0801", "jenniferwatts", 0.90),
    ("Andrew Park", "Andrew", "Park", "Senior Director of SRE", "Director", "andrew.park", "+1-503-555-0901", "andrewpark", 0.84),
    ("Sophie Laurent", "Sophie", "Laurent", "Chief Technology Officer", "C-Suite", "sophie.laurent", "+44-20-7946-0101", "sophielaurent", 0.93),
    ("Pieter van den Berg", "Pieter", "van den Berg", "Head of Payments", "Head", "pieter.vandenberg", "+31-20-555-0201", "pietervandenberg", 0.88),
    ("Klaus Richter", "Klaus", "Richter", "VP of Compliance", "VP", "klaus.richter", "+49-69-555-0301", "klausrichter", 0.91),
    ("Oliver Hayes", "Oliver", "Hayes", "CTO", "C-Suite", "oliver.hayes", "+44-131-555-0401", "oliverhayes", 0.90),
    ("Marie Dubois", "Marie", "Dubois", "Head of Engineering", "Head", "marie.dubois", "+33-1-555-0501", "mariedubois", 0.89),
    ("Hans Weber", "Hans", "Weber", "Director of Product", "Director", "hans.weber", "+49-30-555-0601", "hansweber", 0.86),
    ("Priya Sharma", "Priya", "Sharma", "Chief Technology Officer", "C-Suite", "priya.sharma", "+91-80-555-0701", "priyasharma", 0.94),
    ("Wei Lin", "Wei", "Lin", "VP of Digital Health", "VP", "wei.lin", "+65-555-0801", "weilin", 0.90),
    ("James Cook", "James", "Cook", "Head of Engineering", "Head", "james.cook", "+61-2-555-0901", "jamescook", 0.87),
    ("Yuki Tanaka", "Yuki", "Tanaka", "Director of R&D", "Director", "yuki.tanaka", "+81-3-555-1001", "yukitanaka", 0.88),
    ("Rahul Gupta", "Rahul", "Gupta", "VP of Product", "VP", "rahul.gupta", "+91-22-555-1101", "rahulgupta", 0.86),
    ("Nisha Reddy", "Nisha", "Reddy", "Head of AI/ML", "Head", "nisha.reddy", "+91-80-555-1201", "nishareddy", 0.85),
    ("Daniel Brown", "Daniel", "Brown", "CTO", "C-Suite", "daniel.brown", "+1-650-555-1301", "danielbrown", 0.92),
    ("Amy Zhang", "Amy", "Zhang", "VP of Engineering", "VP", "amy.zhang", "+1-408-555-1401", "amyzhang", 0.90),
]

# Pipeline stages for CompanyStageResult
STAGES = ["industry_discovery", "firmographic_fit", "budget_signals", "urgency_signals", "contact_discovery"]

STAGE_EVIDENCE = {
    "industry_discovery": [
        {"signal": "Company operates in target industry vertical", "description": "Confirmed via website analysis and Crunchbase data", "source_url": "https://crunchbase.com", "tool": "exa_tool", "confidence": 0.92},
        {"signal": "Active in SaaS/cloud market", "description": "Multiple product listings on G2 and Capterra", "source_url": "https://g2.com", "tool": "tavily_tool", "confidence": 0.88},
    ],
    "firmographic_fit": [
        {"signal": "Employee count within target range", "description": "LinkedIn data confirms headcount", "source_url": "https://linkedin.com", "tool": "apollo_tool", "confidence": 0.90},
        {"signal": "Revenue estimate matches criteria", "description": "Financial data from public filings and estimates", "source_url": "https://pitchbook.com", "tool": "exa_tool", "confidence": 0.85},
    ],
    "budget_signals": [
        {"signal": "Recent Series C funding of $75M", "description": "Announced Q4 2025 fundraise led by Sequoia Capital", "source_url": "https://techcrunch.com", "tool": "tavily_tool", "confidence": 0.95},
        {"signal": "Expanding engineering team", "description": "15+ open engineering roles on careers page", "source_url": "https://company.com/careers", "tool": "web_scraper_tool", "confidence": 0.88},
    ],
    "urgency_signals": [
        {"signal": "New CTO appointed 3 months ago", "description": "Leadership change signals potential technology transformation", "source_url": "https://linkedin.com", "tool": "apollo_tool", "confidence": 0.91},
        {"signal": "Cloud migration initiative announced", "description": "Blog post detailing multi-cloud strategy", "source_url": "https://company.com/blog", "tool": "web_scraper_tool", "confidence": 0.86},
    ],
    "contact_discovery": [
        {"signal": "Key decision-makers identified", "description": "CTO and VP Engineering profiles found with verified emails", "source_url": "https://hunter.io", "tool": "hunter_tool", "confidence": 0.89},
        {"signal": "LinkedIn profiles verified", "description": "Active LinkedIn presence with recent posts", "source_url": "https://linkedin.com", "tool": "apollo_tool", "confidence": 0.87},
    ],
}


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------
TOOL_REGISTRY_DATA = [
    {"tool_name": "apollo_tool", "display_name": "Apollo.io", "category": "pipeline", "requires_api_key": True, "api_key_env_var": "APOLLO_API_KEY", "base_url": "https://api.apollo.io/v1", "health_status": "healthy", "priority": 90, "is_enabled": True},
    {"tool_name": "exa_tool", "display_name": "Exa.ai", "category": "pipeline", "requires_api_key": True, "api_key_env_var": "EXA_API_KEY", "base_url": "https://api.exa.ai", "health_status": "healthy", "priority": 85, "is_enabled": True},
    {"tool_name": "hunter_tool", "display_name": "Hunter.io", "category": "pipeline", "requires_api_key": True, "api_key_env_var": "HUNTER_API_KEY", "base_url": "https://api.hunter.io/v2", "health_status": "healthy", "priority": 80, "is_enabled": True},
    {"tool_name": "lusha_tool", "display_name": "Lusha", "category": "pipeline", "requires_api_key": True, "api_key_env_var": "LUSHA_API_KEY", "base_url": "https://api.lusha.com", "health_status": "healthy", "priority": 75, "is_enabled": True},
    {"tool_name": "tavily_tool", "display_name": "Tavily", "category": "pipeline", "requires_api_key": True, "api_key_env_var": "TAVILY_API_KEY", "base_url": "https://api.tavily.com", "health_status": "healthy", "priority": 70, "is_enabled": True},
    {"tool_name": "duckduckgo_tool", "display_name": "DuckDuckGo", "category": "pipeline", "requires_api_key": False, "health_status": "healthy", "priority": 50, "is_enabled": True},
    {"tool_name": "web_scraper_tool", "display_name": "Web Scraper", "category": "pipeline", "requires_api_key": False, "health_status": "healthy", "priority": 60, "is_enabled": True},
    {"tool_name": "linkedin_search_tool", "display_name": "LinkedIn Search", "category": "research", "requires_api_key": False, "health_status": "healthy", "priority": 65, "is_enabled": True},
    {"tool_name": "google_places_tool", "display_name": "Google Places", "category": "research", "requires_api_key": True, "api_key_env_var": "GOOGLE_PLACES_API_KEY", "base_url": "https://maps.googleapis.com", "health_status": "no_api_key", "priority": 40, "is_enabled": True},
    {"tool_name": "sec_tool", "display_name": "SEC EDGAR", "category": "research", "requires_api_key": False, "health_status": "healthy", "priority": 55, "is_enabled": True},
    {"tool_name": "opencorporates_tool", "display_name": "OpenCorporates", "category": "research", "requires_api_key": False, "health_status": "healthy", "priority": 45, "is_enabled": True},
    {"tool_name": "simfin_tool", "display_name": "SimFin", "category": "research", "requires_api_key": True, "api_key_env_var": "SIMFIN_API_KEY", "health_status": "healthy", "priority": 50, "is_enabled": True},
    {"tool_name": "fmp_tool", "display_name": "Financial Modeling Prep", "category": "research", "requires_api_key": True, "api_key_env_var": "FMP_API_KEY", "health_status": "no_api_key", "priority": 35, "is_enabled": True},
    {"tool_name": "news_sentiment_tool", "display_name": "News Sentiment", "category": "research", "requires_api_key": True, "api_key_env_var": "NEWS_API_KEY", "health_status": "healthy", "priority": 55, "is_enabled": True},
    {"tool_name": "company_research_tool", "display_name": "Company Research", "category": "research", "requires_api_key": False, "health_status": "healthy", "priority": 60, "is_enabled": True},
    {"tool_name": "find_executives_tool", "display_name": "Find Executives", "category": "research", "requires_api_key": False, "health_status": "healthy", "priority": 55, "is_enabled": True},
    {"tool_name": "yc_tool", "display_name": "Y Combinator", "category": "research", "requires_api_key": False, "health_status": "healthy", "priority": 40, "is_enabled": True},
    {"tool_name": "search_companies_semantic", "display_name": "Semantic Search", "category": "copilot_db", "requires_api_key": False, "health_status": "healthy", "priority": 70, "is_enabled": True},
]


# ---------------------------------------------------------------------------
# Main seeding function
# ---------------------------------------------------------------------------
async def seed():
    async with async_session() as db:
        # --- Cleanup: delete seeded records by email domain ---
        print("Cleaning up previous seed data...")

        # Find existing seed users
        result = await db.execute(select(User).where(User.email.in_(SEED_EMAILS)))
        existing_users = result.scalars().all()
        existing_user_ids = [u.id for u in existing_users]

        if existing_user_ids:
            # Delete audit logs for these users
            await db.execute(delete(AuditLog).where(AuditLog.user_id.in_(existing_user_ids)))

            # Delete pipeline runs (cascade deletes companies, contacts, stage results, logs)
            runs_result = await db.execute(
                select(PipelineRun).where(PipelineRun.user_id.in_(existing_user_ids))
            )
            for run in runs_result.scalars().all():
                await db.delete(run)

            # Delete ICP configs
            await db.execute(delete(ICPConfig).where(ICPConfig.user_id.in_(existing_user_ids)))

            # Delete users
            await db.execute(delete(User).where(User.id.in_(existing_user_ids)))

        # Delete tool registry and tool effectiveness (global, always re-seed)
        await db.execute(delete(ToolRegistry))
        await db.execute(delete(ToolEffectiveness))

        await db.commit()
        print("  Cleaned.")

        # --- Create Users ---
        print("Creating users...")
        users = build_users()
        for u in users:
            db.add(u)
        await db.flush()
        super_admin = users[0]
        admin_user = users[1]
        regular_user = users[2]
        print(f"  Created {len(users)} users. Super admin: {super_admin.email} ({super_admin.id})")

        # --- Create ICP Configs ---
        print("Creating ICP configs...")
        icps = []
        icp_owners = [super_admin, regular_user, admin_user]
        for i, icp_data in enumerate(ICP_CONFIGS_DATA):
            icp = ICPConfig(
                id=uuid.uuid4(),
                name=icp_data["name"],
                description=icp_data["description"],
                config_json=icp_data["config_json"],
                is_active=True,
                user_id=icp_owners[i].id,
                created_at=_ago(days=30 - i * 10),
            )
            db.add(icp)
            icps.append(icp)
        await db.flush()
        print(f"  Created {len(icps)} ICP configs.")

        # --- Create Pipeline Runs ---
        print("Creating pipeline runs...")
        runs = []
        # Run 1: completed (US Enterprise SaaS)
        run1 = PipelineRun(
            id=uuid.uuid4(),
            icp_config_id=icps[0].id,
            status="completed",
            current_stage="contact_discovery",
            companies_found=15,
            contacts_found=38,
            started_at=_ago(days=5, hours=2),
            completed_at=_ago(days=5, hours=1, minutes=52),
            stage_details={
                "industry_discovery": {"status": "completed", "companies_found": 22},
                "firmographic_fit": {"status": "completed", "companies_passed": 18},
                "budget_signals": {"status": "completed", "companies_scored": 18},
                "urgency_signals": {"status": "completed", "companies_scored": 18},
                "contact_discovery": {"status": "completed", "contacts_found": 38},
            },
            signal_mode="both",
            signal_phase="second_signal_done",
            user_id=super_admin.id,
        )
        runs.append(run1)

        # Run 2: completed (European FinTech)
        run2 = PipelineRun(
            id=uuid.uuid4(),
            icp_config_id=icps[1].id,
            status="completed",
            current_stage="contact_discovery",
            companies_found=10,
            contacts_found=24,
            started_at=_ago(days=3, hours=4),
            completed_at=_ago(days=3, hours=3, minutes=48),
            stage_details={
                "industry_discovery": {"status": "completed", "companies_found": 16},
                "firmographic_fit": {"status": "completed", "companies_passed": 12},
                "budget_signals": {"status": "completed", "companies_scored": 12},
                "urgency_signals": {"status": "completed", "companies_scored": 12},
                "contact_discovery": {"status": "completed", "contacts_found": 24},
            },
            signal_mode="both",
            signal_phase="second_signal_done",
            user_id=regular_user.id,
        )
        runs.append(run2)

        # Run 3: running (APAC Healthcare)
        run3 = PipelineRun(
            id=uuid.uuid4(),
            icp_config_id=icps[2].id,
            status="running",
            current_stage="budget_signals",
            companies_found=5,
            contacts_found=0,
            started_at=_ago(minutes=8),
            stage_details={
                "industry_discovery": {"status": "completed", "companies_found": 10},
                "firmographic_fit": {"status": "completed", "companies_passed": 7},
                "budget_signals": {"status": "in_progress", "companies_scored": 3},
            },
            signal_mode="budget_first",
            user_id=admin_user.id,
        )
        runs.append(run3)

        # Run 4: failed (duplicate of US Enterprise SaaS — simulates a retry)
        run4 = PipelineRun(
            id=uuid.uuid4(),
            icp_config_id=icps[0].id,
            status="failed",
            current_stage="industry_discovery",
            companies_found=0,
            contacts_found=0,
            started_at=_ago(days=7),
            completed_at=_ago(days=7, minutes=-2),
            error_log="API rate limit exceeded on Apollo.io during industry discovery stage. Retry after 60 seconds.",
            stage_details={
                "industry_discovery": {"status": "failed", "error": "Rate limit exceeded"},
            },
            signal_mode="both",
            user_id=super_admin.id,
        )
        runs.append(run4)

        for r in runs:
            db.add(r)
        await db.flush()
        print(f"  Created {len(runs)} pipeline runs.")

        # --- Create Companies, Contacts, and Stage Results ---
        print("Creating companies, contacts, and stage results...")
        company_count = 0
        contact_count = 0
        stage_result_count = 0
        contact_idx = 0
        first_company_id = None

        # Map companies to runs
        run_company_ranges = [
            (run1, COMPANIES_DATA[:15]),   # 15 for run1
            (run2, COMPANIES_DATA[15:25]), # 10 for run2
            (run3, COMPANIES_DATA[25:30]), # 5 for run3 (running)
        ]

        for run, companies_for_run in run_company_ranges:
            for rank, comp_data in enumerate(companies_for_run, start=1):
                comp = Company(
                    id=uuid.uuid4(),
                    pipeline_run_id=run.id,
                    name=comp_data["name"],
                    website=comp_data["website"],
                    industry=comp_data["industry"],
                    city=comp_data["city"],
                    state_region=comp_data["state_region"],
                    country=comp_data["country"],
                    employee_count=comp_data["employee_count"],
                    revenue_estimate=comp_data["revenue_estimate"],
                    description=comp_data["description"],
                    qualification=comp_data["qualification"],
                    icp_match_score=comp_data["icp_match_score"],
                    budget_signal_score=comp_data["budget_signal_score"],
                    urgency_signal_score=comp_data["urgency_signal_score"],
                    final_score=comp_data["final_score"],
                    deal_hotness_score=comp_data["deal_hotness_score"],
                    deal_hotness_tier=comp_data["deal_hotness_tier"],
                    final_rank=rank,
                    current_stage="contact_discovery" if run.status == "completed" else "budget_signals",
                    source="apollo_tool",
                    data_freshness=_ago(days=2),
                    avg_evidence_age_months=2.5,
                )
                db.add(comp)
                await db.flush()
                company_count += 1

                if first_company_id is None:
                    first_company_id = comp.id

                # Create 2-3 contacts per company
                num_contacts = 2 if rank % 3 == 0 else 3
                for j in range(num_contacts):
                    ct = CONTACT_TEMPLATES[contact_idx % len(CONTACT_TEMPLATES)]
                    contact_idx += 1

                    # Build email from company website domain
                    domain = comp_data["website"].replace("https://", "").replace("http://", "")
                    contact = Contact(
                        id=uuid.uuid4(),
                        company_id=comp.id,
                        full_name=ct[0],
                        first_name=ct[1],
                        last_name=ct[2],
                        designation=ct[3],
                        role_category=ct[4],
                        email=f"{ct[5]}@{domain}",
                        phone=ct[6],
                        linkedin_url=f"https://linkedin.com/in/{ct[7]}",
                        source="hunter_tool",
                        confidence=ct[8],
                        enrichment_status="verified",
                    )
                    db.add(contact)
                    contact_count += 1

                # Create stage results for each company
                for stage in STAGES:
                    # Running run only has stages up to budget_signals
                    if run.status == "running" and stage in ("urgency_signals", "contact_discovery"):
                        continue

                    stage_status = "passed"
                    score = comp_data["icp_match_score"] + (hash(stage + comp_data["name"]) % 10 - 5)
                    score = max(40, min(100, score))

                    sr = CompanyStageResult(
                        id=uuid.uuid4(),
                        company_id=comp.id,
                        stage=stage,
                        status=stage_status,
                        score=score,
                        reasoning=f"Company {comp_data['name']} passed {stage.replace('_', ' ')} with strong indicators.",
                        evidence=STAGE_EVIDENCE.get(stage, []),
                    )
                    db.add(sr)
                    stage_result_count += 1

        await db.flush()
        print(f"  Created {company_count} companies, {contact_count} contacts, {stage_result_count} stage results.")

        # --- Create Tool Registry ---
        print("Creating tool registry...")
        health_check_time = _ago(hours=2)
        for td in TOOL_REGISTRY_DATA:
            tool = ToolRegistry(
                id=uuid.uuid4(),
                tool_name=td["tool_name"],
                display_name=td["display_name"],
                category=td["category"],
                requires_api_key=td.get("requires_api_key", False),
                api_key_env_var=td.get("api_key_env_var"),
                base_url=td.get("base_url"),
                is_enabled=td.get("is_enabled", True),
                health_status=td["health_status"],
                last_health_check_at=health_check_time,
                last_health_message="OK" if td["health_status"] == "healthy" else (
                    "API key not configured" if td["health_status"] == "no_api_key" else "Unknown"
                ),
                priority=td.get("priority", 50),
            )
            db.add(tool)

        # Tool effectiveness entries
        for td in TOOL_REGISTRY_DATA[:7]:  # pipeline tools
            te = ToolEffectiveness(
                id=uuid.uuid4(),
                tool_name=td["tool_name"],
                industry="Enterprise SaaS",
                country="United States",
                total_companies_sourced=25 + hash(td["tool_name"]) % 20,
                companies_passed_stage2=15 + hash(td["tool_name"]) % 10,
                avg_final_score=72.0 + hash(td["tool_name"]) % 20,
                total_runs_used=3 + hash(td["tool_name"]) % 5,
                effectiveness_score=65.0 + hash(td["tool_name"]) % 25,
            )
            db.add(te)

        await db.flush()
        print(f"  Created {len(TOOL_REGISTRY_DATA)} tool registry entries.")

        # --- Create Audit Logs ---
        print("Creating audit logs...")
        audit_logs = [
            AuditLog(id=uuid.uuid4(), user_id=super_admin.id, action="create", resource_type="icp_config", resource_id=icps[0].id, details={"name": icps[0].name}, ip_address="192.168.1.10", created_at=_ago(days=30)),
            AuditLog(id=uuid.uuid4(), user_id=regular_user.id, action="create", resource_type="icp_config", resource_id=icps[1].id, details={"name": icps[1].name}, ip_address="192.168.1.20", created_at=_ago(days=20)),
            AuditLog(id=uuid.uuid4(), user_id=admin_user.id, action="create", resource_type="icp_config", resource_id=icps[2].id, details={"name": icps[2].name}, ip_address="192.168.1.30", created_at=_ago(days=10)),
            AuditLog(id=uuid.uuid4(), user_id=super_admin.id, action="update", resource_type="icp_config", resource_id=icps[0].id, details={"changes": ["Updated target roles"]}, ip_address="192.168.1.10", created_at=_ago(days=25)),
            AuditLog(id=uuid.uuid4(), user_id=super_admin.id, action="run_pipeline", resource_type="pipeline_run", resource_id=run1.id, details={"icp_name": icps[0].name}, ip_address="192.168.1.10", created_at=_ago(days=5)),
            AuditLog(id=uuid.uuid4(), user_id=regular_user.id, action="run_pipeline", resource_type="pipeline_run", resource_id=run2.id, details={"icp_name": icps[1].name}, ip_address="192.168.1.20", created_at=_ago(days=3)),
            AuditLog(id=uuid.uuid4(), user_id=admin_user.id, action="run_pipeline", resource_type="pipeline_run", resource_id=run3.id, details={"icp_name": icps[2].name}, ip_address="192.168.1.30", created_at=_ago(minutes=8)),
            AuditLog(id=uuid.uuid4(), user_id=super_admin.id, action="invite_user", resource_type="user", resource_id=regular_user.id, details={"email": regular_user.email, "role": "user"}, ip_address="192.168.1.10", created_at=_ago(days=28)),
            AuditLog(id=uuid.uuid4(), user_id=super_admin.id, action="invite_user", resource_type="user", resource_id=admin_user.id, details={"email": admin_user.email, "role": "admin"}, ip_address="192.168.1.10", created_at=_ago(days=27)),
            AuditLog(id=uuid.uuid4(), user_id=super_admin.id, action="update_role", resource_type="user", resource_id=admin_user.id, details={"old_role": "user", "new_role": "admin"}, ip_address="192.168.1.10", created_at=_ago(days=26)),
            AuditLog(id=uuid.uuid4(), user_id=super_admin.id, action="deactivate_user", resource_type="user", resource_id=users[5].id, details={"email": users[5].email}, ip_address="192.168.1.10", created_at=_ago(days=15)),
            AuditLog(id=uuid.uuid4(), user_id=admin_user.id, action="export_leads", resource_type="pipeline_run", resource_id=run1.id, details={"format": "xlsx", "companies": 15}, ip_address="192.168.1.30", created_at=_ago(days=4)),
        ]
        for al in audit_logs:
            db.add(al)
        await db.flush()
        print(f"  Created {len(audit_logs)} audit logs.")

        await db.commit()

        # --- Summary ---
        print("\n" + "=" * 60)
        print("SEED DATA SUMMARY")
        print("=" * 60)
        print(f"Users:          {len(users)}")
        print(f"ICP Configs:    {len(icps)}")
        print(f"Pipeline Runs:  {len(runs)}")
        print(f"Companies:      {company_count}")
        print(f"Contacts:       {contact_count}")
        print(f"Stage Results:  {stage_result_count}")
        print(f"Tool Registry:  {len(TOOL_REGISTRY_DATA)}")
        print(f"Audit Logs:     {len(audit_logs)}")
        print()
        print("KEY IDS FOR PLAYWRIGHT:")
        print(f"  Super admin email:     {super_admin.email}")
        print(f"  Regular user email:    {regular_user.email}")
        print(f"  Completed run 1 ID:    {run1.id}")
        print(f"  Completed run 2 ID:    {run2.id}")
        print(f"  First company ID:      {first_company_id}")
        print(f"  ICP 1 (US SaaS) ID:    {icps[0].id}")
        print(f"  ICP 2 (EU FinTech) ID: {icps[1].id}")
        print("=" * 60)


def main():
    asyncio.run(seed())


if __name__ == "__main__":
    main()
