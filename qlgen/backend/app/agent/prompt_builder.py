import json


def build_pipeline_prompt(icp: dict, options: dict) -> str:
    """Convert ICP config + options into a full agent prompt."""
    max_companies = options.get("max_companies", 25)
    max_contacts = options.get("max_contacts_per_company", 5)

    sections = []
    sections.append(f"""Execute the full lead generation pipeline for the following Ideal Customer Profile.
Find {max_companies} qualified companies with up to {max_contacts} contacts each.

══════════════════════════════════════
IDEAL CUSTOMER PROFILE
══════════════════════════════════════""")

    if "target_offering" in icp:
        sections.append(f"1. TARGET OFFERING:\n{json.dumps(icp['target_offering'], indent=2)}")

    if "regions" in icp:
        sections.append(f"2. TARGET REGIONS:\n{json.dumps(icp['regions'], indent=2)}")

    if "industry_types" in icp:
        sections.append(f"3. INDUSTRY TYPES & VERTICALS:\n{json.dumps(icp['industry_types'], indent=2)}")

    if "company_size" in icp:
        cs = icp["company_size"]
        emp_min = cs.get("employees_min", "N/A")
        emp_max = cs.get("employees_max", "N/A")
        rev_min = cs.get("revenue_min", "N/A")
        rev_max = cs.get("revenue_max", "N/A")
        currency = cs.get("revenue_currency", "USD")
        sections.append(
            f"4. COMPANY SIZE:\n"
            f"   - Employees: {emp_min:,} to {emp_max:,}\n"
            f"   - Revenue: {currency} {rev_min:,} to {rev_max:,}"
            if isinstance(emp_min, int) and isinstance(rev_min, int)
            else f"4. COMPANY SIZE:\n{json.dumps(cs, indent=2)}"
        )

    if "technology_maturity" in icp:
        tm = icp["technology_maturity"]
        sections.append(
            f"5. TECHNOLOGY MATURITY SIGNALS:\n"
            f"   Positive signals: {json.dumps(tm.get('signals', []))}\n"
            f"   Negative signals: {json.dumps(tm.get('negative_signals', []))}"
        )

    if "infrastructure_readiness" in icp:
        sections.append(f"6. INFRASTRUCTURE READINESS:\n{json.dumps(icp['infrastructure_readiness'], indent=2)}")

    if "digital_transformation_drivers" in icp:
        dtd = icp["digital_transformation_drivers"]
        sections.append(
            f"7. DIGITAL TRANSFORMATION DRIVERS:\n"
            f"   Growth triggers: {json.dumps(dtd.get('growth_triggers', []))}\n"
            f"   Operational pains: {json.dumps(dtd.get('operational_pains', []))}\n"
            f"   Competitive pressures: {json.dumps(dtd.get('competitive_pressures', []))}\n"
            f"   Strategic initiatives: {json.dumps(dtd.get('strategic_initiatives', []))}"
        )

    if "leadership_traits" in icp:
        lt = icp["leadership_traits"]
        sections.append(
            f"8. LEADERSHIP TRAITS:\n"
            f"   Target roles: {json.dumps(lt.get('target_roles', []))}\n"
            f"   Behavioral traits: {json.dumps(lt.get('behavioral_traits', []))}"
        )

    sections.append("""══════════════════════════════════════
INSTRUCTIONS
══════════════════════════════════════
Now execute all 4 stages (Company Discovery → Contact Discovery → Enrichment → BANT Scoring)
and return the complete results as the JSON structure defined in your system prompt.

Begin with Stage 1: Company Discovery.""")

    return "\n\n".join(sections)
