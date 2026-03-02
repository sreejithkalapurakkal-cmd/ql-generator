"""Service for generating ICP Excel templates and parsing uploaded ICP Excel files."""

from io import BytesIO
from typing import List
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
HEADER_FILL = PatternFill(start_color="5C2D8F", end_color="5C2D8F", fill_type="solid")
EXAMPLE_FONT = Font(name="Calibri", italic=True, color="888888", size=10)
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
THIN_BORDER = Border(
    left=Side(style="thin", color="D6D6D6"),
    right=Side(style="thin", color="D6D6D6"),
    top=Side(style="thin", color="D6D6D6"),
    bottom=Side(style="thin", color="D6D6D6"),
)


def _style_header_row(ws, num_cols: int):
    """Apply header styling to the first row."""
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGNMENT
        cell.border = THIN_BORDER


def _style_example_rows(ws, start_row: int, end_row: int, num_cols: int):
    """Style example data rows."""
    for row in range(start_row, end_row + 1):
        for col in range(1, num_cols + 1):
            cell = ws.cell(row=row, column=col)
            cell.font = EXAMPLE_FONT
            cell.border = THIN_BORDER


def generate_icp_template() -> BytesIO:
    """Generate a multi-ICP Excel template with 8 sheets."""
    wb = Workbook()

    # Sheet 1: Overview
    ws = wb.active
    ws.title = "Overview"
    ws.append(["ICP Name", "Description"])
    ws.append(["Enterprise SaaS - US", "Target mid-market SaaS companies in the US for our analytics platform"])
    ws.append(["SMB Ecommerce - EU", "Target growing ecommerce businesses in Europe"])
    _style_header_row(ws, 2)
    _style_example_rows(ws, 2, 3, 2)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 60

    # Sheet 2: Offerings
    ws = wb.create_sheet("Offerings")
    ws.append(["ICP Name", "Target Offering"])
    ws.append(["Enterprise SaaS - US", "Cloud analytics platform"])
    ws.append(["Enterprise SaaS - US", "Data pipeline automation"])
    ws.append(["SMB Ecommerce - EU", "Headless commerce platform"])
    ws.append(["SMB Ecommerce - EU", "Order management system"])
    _style_header_row(ws, 2)
    _style_example_rows(ws, 2, 5, 2)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 40

    # Sheet 3: Regions
    ws = wb.create_sheet("Regions")
    ws.append(["ICP Name", "Country", "Priority Area"])
    ws.append(["Enterprise SaaS - US", "United States", "San Francisco Bay Area"])
    ws.append(["Enterprise SaaS - US", "United States", "New York"])
    ws.append(["SMB Ecommerce - EU", "Germany", "Berlin"])
    ws.append(["SMB Ecommerce - EU", "United Kingdom", "London"])
    _style_header_row(ws, 3)
    _style_example_rows(ws, 2, 5, 3)
    for c in ["A", "B", "C"]:
        ws.column_dimensions[c].width = 30

    # Sheet 4: Industries
    ws = wb.create_sheet("Industries")
    ws.append(["ICP Name", "Vertical", "Sub-Vertical"])
    ws.append(["Enterprise SaaS - US", "Technology", "SaaS / Cloud"])
    ws.append(["Enterprise SaaS - US", "Technology", "Data & Analytics"])
    ws.append(["SMB Ecommerce - EU", "Retail", "Ecommerce"])
    ws.append(["SMB Ecommerce - EU", "Retail", "Fashion & Apparel"])
    _style_header_row(ws, 3)
    _style_example_rows(ws, 2, 5, 3)
    for c in ["A", "B", "C"]:
        ws.column_dimensions[c].width = 30

    # Sheet 5: Company Size
    ws = wb.create_sheet("Company Size")
    ws.append(["ICP Name", "Employees Min", "Employees Max", "Revenue Min", "Revenue Max", "Revenue Currency"])
    ws.append(["Enterprise SaaS - US", 200, 5000, 20000000, 500000000, "USD"])
    ws.append(["SMB Ecommerce - EU", 20, 500, 2000000, 50000000, "EUR"])
    _style_header_row(ws, 6)
    _style_example_rows(ws, 2, 3, 6)
    ws.column_dimensions["A"].width = 30
    for c in ["B", "C", "D", "E", "F"]:
        ws.column_dimensions[c].width = 18

    # Sheet 6: Technology
    ws = wb.create_sheet("Technology")
    ws.append(["ICP Name", "Signal (Positive)", "Negative Signal"])
    ws.append(["Enterprise SaaS - US", "AWS", "Legacy on-premise only"])
    ws.append(["Enterprise SaaS - US", "Snowflake", "No cloud adoption"])
    ws.append(["SMB Ecommerce - EU", "Shopify", "Custom-built monolith"])
    ws.append(["SMB Ecommerce - EU", "Klaviyo", ""])
    _style_header_row(ws, 3)
    _style_example_rows(ws, 2, 5, 3)
    for c in ["A", "B", "C"]:
        ws.column_dimensions[c].width = 30

    # Sheet 7: Drivers
    ws = wb.create_sheet("Drivers")
    ws.append(["ICP Name", "Growth Trigger", "Operational Pain", "Competitive Pressure", "Strategic Initiative"])
    ws.append(["Enterprise SaaS - US", "Series B+ funding", "Manual data pipelines", "Competitors using AI", "Digital transformation"])
    ws.append(["SMB Ecommerce - EU", "Revenue doubling", "Fulfillment bottlenecks", "Amazon competition", "International expansion"])
    _style_header_row(ws, 5)
    _style_example_rows(ws, 2, 3, 5)
    ws.column_dimensions["A"].width = 30
    for c in ["B", "C", "D", "E"]:
        ws.column_dimensions[c].width = 28

    # Sheet 8: Leadership
    ws = wb.create_sheet("Leadership")
    ws.append(["ICP Name", "Target Role", "Behavioral Trait"])
    ws.append(["Enterprise SaaS - US", "CTO", "Innovation-driven"])
    ws.append(["Enterprise SaaS - US", "VP Engineering", "Data-oriented"])
    ws.append(["SMB Ecommerce - EU", "Head of Ecommerce", "Growth-focused"])
    ws.append(["SMB Ecommerce - EU", "CEO", "Technology adopter"])
    _style_header_row(ws, 3)
    _style_example_rows(ws, 2, 5, 3)
    for c in ["A", "B", "C"]:
        ws.column_dimensions[c].width = 30

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def _read_column_values(ws, icp_name: str, col_index: int) -> list[str]:
    """Read non-empty values from a column for a specific ICP name."""
    values = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] and str(row[0]).strip() == icp_name:
            val = row[col_index] if len(row) > col_index else None
            if val is not None and str(val).strip():
                values.append(str(val).strip())
    return values


def parse_icp_excel(buffer: BytesIO) -> List[dict]:
    """Parse an uploaded Excel file and return extracted ICP configurations.

    Returns a list of dicts, one per ICP found:
    [{"name": str, "description": str, "config": dict, "warnings": list[str]}]
    """
    wb = load_workbook(buffer, read_only=True, data_only=True)
    results = []

    # Get ICP names from the Overview sheet
    overview_ws = wb["Overview"] if "Overview" in wb.sheetnames else wb[wb.sheetnames[0]]
    icp_entries = {}
    for row in overview_ws.iter_rows(min_row=2, values_only=True):
        name = row[0] if row and row[0] else None
        if name and str(name).strip():
            name_str = str(name).strip()
            desc = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            icp_entries[name_str] = desc

    if not icp_entries:
        return [{"name": "", "description": "", "config": {}, "warnings": ["No ICP entries found in Overview sheet"]}]

    for icp_name, description in icp_entries.items():
        warnings = []
        config = {
            "target_offering": [],
            "regions": {"countries": [], "priority_areas": []},
            "industry_types": [],
            "company_size": {
                "employees_min": 50, "employees_max": 1500,
                "revenue_min": 10000000, "revenue_max": 500000000,
                "revenue_currency": "USD",
            },
            "technology_maturity": {"signals": [], "negative_signals": []},
            "infrastructure_readiness": {"indicators": []},
            "digital_transformation_drivers": {
                "growth_triggers": [], "operational_pains": [],
                "competitive_pressures": [], "strategic_initiatives": [],
            },
            "leadership_traits": {"target_roles": [], "behavioral_traits": []},
        }

        # Offerings
        if "Offerings" in wb.sheetnames:
            config["target_offering"] = _read_column_values(wb["Offerings"], icp_name, 1)
        if not config["target_offering"]:
            warnings.append("No target offerings found")

        # Regions
        if "Regions" in wb.sheetnames:
            config["regions"]["countries"] = list(set(_read_column_values(wb["Regions"], icp_name, 1)))
            config["regions"]["priority_areas"] = _read_column_values(wb["Regions"], icp_name, 2)
        if not config["regions"]["countries"]:
            warnings.append("No target regions/countries found")

        # Industries
        if "Industries" in wb.sheetnames:
            ws = wb["Industries"]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row[0] and str(row[0]).strip() == icp_name:
                    vertical = str(row[1]).strip() if len(row) > 1 and row[1] else None
                    sub_vertical = str(row[2]).strip() if len(row) > 2 and row[2] else None
                    if vertical:
                        config["industry_types"].append({
                            "vertical": vertical,
                            "sub_vertical": sub_vertical,
                        })

        # Company Size
        if "Company Size" in wb.sheetnames:
            ws = wb["Company Size"]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row[0] and str(row[0]).strip() == icp_name:
                    try:
                        config["company_size"] = {
                            "employees_min": int(row[1]) if len(row) > 1 and row[1] else 50,
                            "employees_max": int(row[2]) if len(row) > 2 and row[2] else 1500,
                            "revenue_min": int(row[3]) if len(row) > 3 and row[3] else 10000000,
                            "revenue_max": int(row[4]) if len(row) > 4 and row[4] else 500000000,
                            "revenue_currency": str(row[5]).strip() if len(row) > 5 and row[5] else "USD",
                        }
                    except (ValueError, TypeError):
                        warnings.append("Invalid numeric values in Company Size sheet")
                    break

        # Technology
        if "Technology" in wb.sheetnames:
            config["technology_maturity"]["signals"] = _read_column_values(wb["Technology"], icp_name, 1)
            config["technology_maturity"]["negative_signals"] = _read_column_values(wb["Technology"], icp_name, 2)

        # Drivers
        if "Drivers" in wb.sheetnames:
            config["digital_transformation_drivers"]["growth_triggers"] = _read_column_values(wb["Drivers"], icp_name, 1)
            config["digital_transformation_drivers"]["operational_pains"] = _read_column_values(wb["Drivers"], icp_name, 2)
            config["digital_transformation_drivers"]["competitive_pressures"] = _read_column_values(wb["Drivers"], icp_name, 3)
            config["digital_transformation_drivers"]["strategic_initiatives"] = _read_column_values(wb["Drivers"], icp_name, 4)

        # Leadership
        if "Leadership" in wb.sheetnames:
            config["leadership_traits"]["target_roles"] = _read_column_values(wb["Leadership"], icp_name, 1)
            config["leadership_traits"]["behavioral_traits"] = _read_column_values(wb["Leadership"], icp_name, 2)

        results.append({
            "name": icp_name,
            "description": description,
            "config": config,
            "warnings": warnings,
        })

    wb.close()
    return results
