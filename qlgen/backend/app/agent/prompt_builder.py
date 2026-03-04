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

    # Support both wizard keys (offering, industry, size, etc.) and legacy keys (target_offering, industry_types, etc.)
    offering = icp.get("target_offering") or icp.get("offering")
    if offering:
        sections.append(f"1. TARGET OFFERING:\n{json.dumps(offering, indent=2)}")

    regions = icp.get("regions")
    if regions:
        sections.append(f"2. TARGET REGIONS:\n{json.dumps(regions, indent=2)}")

    industry = icp.get("industry_types") or icp.get("industry")
    if industry:
        sections.append(f"3. INDUSTRY TYPES & VERTICALS:\n{json.dumps(industry, indent=2)}")

    cs = icp.get("company_size") or icp.get("size")
    if cs:
        emp = cs.get("employee_range") or {}
        emp_min = emp.get("min") if emp else cs.get("employees_min", "N/A")
        emp_max = emp.get("max") if emp else cs.get("employees_max", "N/A")
        rev = cs.get("revenue_range") or {}
        rev_min = rev.get("min") if rev else cs.get("revenue_min", "N/A")
        rev_max = rev.get("max") if rev else cs.get("revenue_max", "N/A")
        sections.append(
            f"4. COMPANY SIZE:\n"
            f"   - Employees: {emp_min} to {emp_max}\n"
            f"   - Revenue: {rev_min} to {rev_max}"
        )

    tm = icp.get("technology_maturity") or icp.get("tech")
    if tm:
        sections.append(
            f"5. TECHNOLOGY MATURITY SIGNALS:\n"
            f"   Positive signals: {json.dumps(tm.get('positive_signals', tm.get('signals', [])))}\n"
            f"   Negative signals: {json.dumps(tm.get('negative_signals', []))}"
        )

    infra = icp.get("infrastructure_readiness") or icp.get("infra")
    if infra:
        sections.append(f"6. INFRASTRUCTURE READINESS:\n{json.dumps(infra, indent=2)}")

    dtd = icp.get("digital_transformation_drivers") or icp.get("drivers")
    if dtd:
        sections.append(
            f"7. DIGITAL TRANSFORMATION DRIVERS:\n"
            f"   Growth triggers: {json.dumps(dtd.get('growth_triggers', []))}\n"
            f"   Operational pains: {json.dumps(dtd.get('pains', dtd.get('operational_pains', [])))}\n"
            f"   Competitive pressures: {json.dumps(dtd.get('pressures', dtd.get('competitive_pressures', [])))}\n"
            f"   Strategic initiatives: {json.dumps(dtd.get('initiatives', dtd.get('strategic_initiatives', [])))}"
        )

    lt = icp.get("leadership_traits") or icp.get("leadership")
    if lt:
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
