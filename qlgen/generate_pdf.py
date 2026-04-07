#!/usr/bin/env python3
"""Generate qlGen User Guide PDF with embedded screenshots using fpdf2."""

import os
from fpdf import FPDF
from PIL import Image

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "frontend", "screenshots")
OUTPUT_PDF = os.path.join(os.path.dirname(__file__), "frontend", "public", "qlGen-User-Guide.pdf")


class UserGuidePDF(FPDF):
    """Custom PDF class for the qlGen User Guide."""

    PURPLE = (107, 56, 202)
    DARK = (33, 33, 33)
    GRAY = (100, 100, 100)
    LIGHT_BG = (248, 245, 255)
    TABLE_HEADER_BG = (107, 56, 202)
    TABLE_ROW_ALT = (245, 243, 255)
    WHITE = (255, 255, 255)
    TIP_BG = (240, 253, 244)
    TIP_BORDER = (34, 197, 94)
    NOTE_BG = (254, 249, 234)
    NOTE_BORDER = (234, 179, 8)
    ORANGE = (234, 88, 12)

    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(20, 20, 20)

        # Add fonts
        self.add_font("Inter", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True)
        self.add_font("Inter", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", uni=True)
        self.add_font("Inter", "I", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf", uni=True)
        self.add_font("InterMono", "", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", uni=True)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Inter", "B", 8)
        self.set_text_color(*self.PURPLE)
        self.cell(0, 8, "qlGen User Guide", align="L")
        self.set_font("Inter", "", 8)
        self.set_text_color(*self.GRAY)
        self.cell(0, 8, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.PURPLE)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Inter", "", 7)
        self.set_text_color(*self.GRAY)
        self.cell(0, 10, "Confidential - Gadgeon Smart Systems", align="C")

    def add_cover_page(self):
        self.add_page()
        self.ln(50)
        self.set_font("Inter", "B", 36)
        self.set_text_color(*self.PURPLE)
        self.cell(0, 16, "qlGen", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Inter", "B", 18)
        self.set_text_color(*self.DARK)
        self.cell(0, 10, "User Guide", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)
        self.set_font("Inter", "", 13)
        self.set_text_color(*self.GRAY)
        self.cell(0, 8, "AI-Powered Qualified Lead Generation", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(20)

        # Divider
        self.set_draw_color(*self.PURPLE)
        self.set_line_width(0.5)
        self.line(70, self.get_y(), 140, self.get_y())
        self.ln(20)

        self.set_font("Inter", "", 10)
        self.set_text_color(*self.GRAY)
        self.cell(0, 6, "Version 2.0  |  April 2026", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.cell(0, 6, "Gadgeon Smart Systems", align="C", new_x="LMARGIN", new_y="NEXT")

    def section_title(self, text):
        self.ln(6)
        self.set_font("Inter", "B", 18)
        self.set_text_color(*self.PURPLE)
        self.cell(0, 12, text, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.PURPLE)
        self.set_line_width(0.6)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(6)

    def subsection_title(self, text):
        self.ln(4)
        self.set_font("Inter", "B", 14)
        self.set_text_color(*self.DARK)
        self.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def sub_subsection_title(self, text):
        self.ln(2)
        self.set_font("Inter", "B", 11)
        self.set_text_color(*self.PURPLE)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text):
        self.set_font("Inter", "", 10)
        self.set_text_color(*self.DARK)
        self.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def bold_text(self, text):
        self.set_font("Inter", "B", 10)
        self.set_text_color(*self.DARK)
        self.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def bullet_list(self, items):
        self.set_font("Inter", "", 10)
        self.set_text_color(*self.DARK)
        for item in items:
            x = self.get_x()
            self.cell(6, 6, "\u2022")
            self.multi_cell(0, 6, f" {item}", new_x="LMARGIN", new_y="NEXT")
            self.ln(1)
        self.ln(2)

    def numbered_list(self, items):
        self.set_font("Inter", "", 10)
        self.set_text_color(*self.DARK)
        for i, item in enumerate(items, 1):
            self.cell(8, 6, f"{i}.")
            self.multi_cell(0, 6, f" {item}", new_x="LMARGIN", new_y="NEXT")
            self.ln(1)
        self.ln(2)

    def tip_box(self, text):
        self.ln(2)
        x = self.get_x()
        y = self.get_y()
        self.set_fill_color(*self.TIP_BG)
        self.set_draw_color(*self.TIP_BORDER)
        # Calculate height
        self.set_font("Inter", "", 9)
        # Approx height
        lines = len(text) / 75 + 1
        h = max(lines * 5 + 8, 14)
        self.rect(x, y, 170, h, style="DF")
        self.set_xy(x + 4, y + 3)
        self.set_font("Inter", "B", 9)
        self.set_text_color(34, 130, 60)
        self.cell(10, 5, "Tip: ", new_x="END")
        self.set_font("Inter", "", 9)
        self.set_text_color(*self.DARK)
        self.multi_cell(152, 5, text, new_x="LMARGIN", new_y="NEXT")
        self.set_y(y + h + 2)
        self.ln(2)

    def note_box(self, text):
        self.ln(2)
        x = self.get_x()
        y = self.get_y()
        self.set_fill_color(*self.NOTE_BG)
        self.set_draw_color(*self.NOTE_BORDER)
        self.set_font("Inter", "", 9)
        lines = len(text) / 75 + 1
        h = max(lines * 5 + 8, 14)
        self.rect(x, y, 170, h, style="DF")
        self.set_xy(x + 4, y + 3)
        self.set_font("Inter", "B", 9)
        self.set_text_color(160, 120, 0)
        self.cell(12, 5, "Note: ", new_x="END")
        self.set_font("Inter", "", 9)
        self.set_text_color(*self.DARK)
        self.multi_cell(150, 5, text, new_x="LMARGIN", new_y="NEXT")
        self.set_y(y + h + 2)
        self.ln(2)

    def add_screenshot(self, filename, caption=None, width=160):
        filepath = os.path.join(SCREENSHOTS_DIR, filename)
        if not os.path.exists(filepath):
            self.body_text(f"[Screenshot not found: {filename}]")
            return

        # Get image dimensions to calculate height
        with Image.open(filepath) as img:
            img_w, img_h = img.size
        aspect = img_h / img_w
        display_h = width * aspect

        # Check if we need a new page
        if self.get_y() + display_h + 15 > 277:
            self.add_page()

        self.ln(3)

        # Center the image
        x_offset = (170 - width) / 2 + 20

        # Add subtle border
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        self.rect(x_offset - 1, self.get_y() - 1, width + 2, display_h + 2)

        self.image(filepath, x=x_offset, w=width)
        self.ln(3)

        if caption:
            self.set_font("Inter", "I", 8)
            self.set_text_color(*self.GRAY)
            self.cell(0, 5, caption, align="C", new_x="LMARGIN", new_y="NEXT")
            self.ln(4)

    def simple_table(self, headers, rows, col_widths=None):
        """Draw a simple table with headers and rows."""
        if col_widths is None:
            num_cols = len(headers)
            col_widths = [170 / num_cols] * num_cols

        self.ln(2)
        # Header
        self.set_fill_color(*self.TABLE_HEADER_BG)
        self.set_text_color(*self.WHITE)
        self.set_font("Inter", "B", 9)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 8, header, border=1, fill=True, align="C")
        self.ln()

        # Rows
        self.set_text_color(*self.DARK)
        self.set_font("Inter", "", 9)
        for row_idx, row in enumerate(rows):
            if row_idx % 2 == 1:
                self.set_fill_color(*self.TABLE_ROW_ALT)
                fill = True
            else:
                self.set_fill_color(*self.WHITE)
                fill = True

            max_h = 8
            # Calculate max height needed
            for i, cell_text in enumerate(row):
                lines = self.multi_cell(col_widths[i], 5, cell_text, dry_run=True, output="LINES")
                cell_h = len(lines) * 5 + 2
                max_h = max(max_h, cell_h)

            y_start = self.get_y()
            for i, cell_text in enumerate(row):
                x_start = self.get_x()
                # Draw cell background
                self.rect(x_start, y_start, col_widths[i], max_h, style="DF")
                self.set_xy(x_start + 1, y_start + 1)
                self.multi_cell(col_widths[i] - 2, 5, cell_text)
                self.set_xy(x_start + col_widths[i], y_start)

            self.set_y(y_start + max_h)

        self.ln(4)


def generate_guide():
    pdf = UserGuidePDF()

    # ============================================================
    # COVER PAGE
    # ============================================================
    pdf.add_cover_page()

    # ============================================================
    # TABLE OF CONTENTS
    # ============================================================
    pdf.add_page()
    pdf.section_title("Table of Contents")
    pdf.set_font("Inter", "", 11)
    pdf.set_text_color(*UserGuidePDF.DARK)
    toc_items = [
        ("1.", "What is qlGen?"),
        ("2.", "Navigation"),
        ("3.", "Getting Started: Your First Search"),
        ("4.", "The 7-Step ICP Wizard"),
        ("5.", "LinkedIn Sales Navigator Integration"),
        ("6.", "Pipeline Progress"),
        ("7.", "Viewing Your Results"),
        ("8.", "Understanding BANT Scores"),
        ("9.", "Managing Saved ICPs"),
        ("10.", "Using the Dashboard"),
        ("11.", "AI Co-pilot"),
        ("12.", "Help & Feedback"),
        ("13.", "Admin Features"),
        ("14.", "Bulk Import from Excel"),
        ("15.", "Tips for Better Results"),
        ("16.", "Frequently Asked Questions"),
    ]
    for num, title in toc_items:
        pdf.set_font("Inter", "B", 11)
        pdf.set_text_color(*UserGuidePDF.PURPLE)
        pdf.cell(12, 8, num)
        pdf.set_font("Inter", "", 11)
        pdf.set_text_color(*UserGuidePDF.DARK)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")

    # ============================================================
    # 1. WHAT IS QLGEN?
    # ============================================================
    pdf.add_page()
    pdf.section_title("1. What is qlGen?")
    pdf.body_text(
        "qlGen helps you build a pipeline of qualified leads in minutes. You define your "
        "Ideal Customer Profile (ICP) \u2014 the type of company and decision-maker you want to "
        "sell to \u2014 and qlGen's AI agent automatically:"
    )
    pdf.numbered_list([
        "Discovers companies matching your criteria (via web sources or LinkedIn Sales Navigator)",
        "Finds key contacts (decision-makers) at each company",
        "Enriches contact details \u2014 emails, phone numbers, LinkedIn profiles",
        "Scores every lead using the BANT framework (Budget, Authority, Need, Timing)",
    ])
    pdf.body_text(
        "The result is a sales-ready list you can export to Excel and start working immediately."
    )
    pdf.add_screenshot("01-welcome-page.png", "qlGen Home Page \u2014 Start your search or explore past results")

    # ============================================================
    # 2. NAVIGATION
    # ============================================================
    pdf.add_page()
    pdf.section_title("2. Navigation")
    pdf.body_text(
        "The top navigation bar provides quick access to all sections of the application:"
    )
    pdf.simple_table(
        ["Menu Item", "What It Does"],
        [
            ["Home", "Landing page with quick-start buttons"],
            ["Dashboard", "Overview of searches, stats, and Evaboot credit balance"],
            ["All Leads", "View qualified leads across all searches"],
            ["Saved ICPs", "Your saved Ideal Customer Profiles (reusable)"],
            ["Tools", "Tool availability and rate limits (admin only)"],
            ["Users", "User management (admin only)"],
            ["Feedback", "Feedback management (admin only)"],
        ],
        col_widths=[40, 130],
    )
    pdf.body_text(
        "The top-right corner features a Help menu (question mark icon), your profile avatar, "
        "and the Gadgeon logo. The AI Co-pilot can be opened by clicking the sparkle button "
        "in the bottom-right corner of any page."
    )

    # ============================================================
    # 3. GETTING STARTED
    # ============================================================
    pdf.add_page()
    pdf.section_title("3. Getting Started: Your First Search")

    pdf.subsection_title("Step 1 \u2014 Create a New Search")
    pdf.body_text(
        "From the Home page, click \"Start Your Search\". This opens the ICP Configuration wizard. "
        "Alternatively, click \"+ New Search\" from the Dashboard or the Saved ICPs page."
    )

    pdf.subsection_title("Step 2 \u2014 Fill in the 7-Step ICP Wizard")
    pdf.body_text(
        "The wizard walks you through defining your ideal customer. Each step captures a different "
        "dimension. You can navigate between steps freely by clicking the step numbers on the left sidebar."
    )

    pdf.subsection_title("Step 3 \u2014 Watch the Pipeline Run")
    pdf.body_text(
        "After clicking \"Save & Run Search\", the Pipeline Progress page shows the AI agent working "
        "in real time with a live activity log. You can safely leave \u2014 results are saved automatically."
    )

    pdf.subsection_title("Step 4 \u2014 View Results & Export")
    pdf.body_text(
        "When the search completes, view your results on the Search Results page with Companies, "
        "Pipeline Funnel, Search Criteria, and Search Summary tabs. Export to Excel or CSV anytime."
    )

    # ============================================================
    # 4. THE 7-STEP ICP WIZARD
    # ============================================================
    pdf.add_page()
    pdf.section_title("4. The 7-Step ICP Wizard")

    # Step 1: Discovery Source
    pdf.subsection_title("Step 1: Discovery Source")
    pdf.body_text(
        "Choose how companies should be discovered. This controls Stage 1 (Industry Discovery) "
        "and Stage 2 (Firmographic Fit). Stages 3\u20135 (Signals, Contacts, Scoring) run the same "
        "regardless of your choice."
    )
    pdf.simple_table(
        ["Mode", "Description", "Credits"],
        [
            ["qlGen Multi-Source", "Apollo, Exa, DuckDuckGo, registries, and more. Default mode.", "Free"],
            ["Sales Navigator Only", "Extracts from LinkedIn Sales Navigator via Evaboot. Pipeline fails if extraction fails.", "1 credit/profile"],
            ["Sales Nav + qlGen (Hybrid)", "LinkedIn data combined with qlGen multi-source for max coverage. Falls back to qlGen-only if extraction fails.", "1 credit/profile"],
        ],
        col_widths=[42, 100, 28],
    )
    pdf.add_screenshot("03a-icp-step1-qlgen-mode.png", "Step 1: Discovery Source \u2014 qlGen Multi-Source selected (default)")

    pdf.add_page()
    pdf.sub_subsection_title("Sales Navigator Mode")
    pdf.body_text(
        "When you select a Sales Navigator mode (Sales Navigator Only or Hybrid), additional "
        "options appear:"
    )
    pdf.numbered_list([
        "Evaboot Account Status is displayed \u2014 showing Credits Available, Daily Usage, and Sales Nav Session status",
        "Paste your Sales Navigator URL \u2014 copy the URL from your LinkedIn Sales Navigator search bar",
        "Auto-fill from URL \u2014 qlGen extracts filters (industry, geography, company size, roles) and pre-fills your ICP fields",
        "\"Fill remaining with AI\" button \u2014 AI generates missing fields (urgency signals, budget signals, etc.) based on context",
    ])
    pdf.add_screenshot("03b-icp-step1-sales-nav-selected.png", "Sales Navigator Only selected \u2014 Evaboot account status and URL input")

    pdf.add_page()
    pdf.sub_subsection_title("Auto-Fill from Sales Navigator URL")
    pdf.body_text(
        "When you paste a Sales Navigator search URL, qlGen automatically extracts the filters and "
        "pre-fills your ICP wizard fields. You'll see a green summary showing which filters were "
        "extracted (Industry, Company Headcount, Region) and which fields still need input."
    )
    pdf.add_screenshot("03c-icp-step1-url-parsed.png", "Filters extracted from Sales Navigator URL \u2014 Industry, headcount, and region auto-filled")

    pdf.tip_box(
        "Narrow your search in Sales Navigator first to control Evaboot credit usage. "
        "The more targeted your search, the fewer credits consumed."
    )
    pdf.note_box(
        "Saved list URLs don't contain filter parameters, so auto-fill won't work. "
        "Use a search URL instead, or fill fields manually."
    )

    # Step 2: Firmographics
    pdf.add_page()
    pdf.subsection_title("Step 2: Firmographics")
    pdf.body_text(
        "This step defines your company targeting criteria. When using Sales Navigator mode, "
        "an info banner reminds you that discovery is handled by your Sales Nav URL \u2014 these "
        "criteria are used by the AI agent to score each company's fit."
    )
    pdf.bullet_list([
        "Name (required): Give this search a descriptive name",
        "Description: Optional short summary",
        "Industry Verticals: Add one or more with optional sub-verticals",
        "Target Countries: e.g., United States, United Kingdom",
        "Employee Count Range: Min and max headcount",
        "Revenue Range: Currency, min, and max revenue",
        "Low Cost Center: Toggle for companies with low-cost center operations",
    ])
    pdf.add_screenshot("04-icp-step2-firmographics.png", "Step 2: Firmographics \u2014 auto-filled from Sales Navigator URL")

    pdf.tip_box(
        "Click \"Create with AI / Upload\" at the top to pre-fill the wizard. "
        "You can describe your ideal customer in plain English or upload a file (PDF, DOCX, XLSX, TXT, CSV)."
    )

    # Step 3: Capability
    pdf.add_page()
    pdf.subsection_title("Step 3: Capability")
    pdf.body_text(
        "Define the products or services you want to sell (Target Offerings / Service Areas). "
        "Press Enter or click \"Add\" after typing each one. Choose AND (company must match ALL) "
        "or OR (company must match ANY)."
    )
    pdf.add_screenshot("05-icp-step3-capability.png", "Step 3: Capability \u2014 Target offerings and match condition")

    # Step 4: Urgency
    pdf.subsection_title("Step 4: Urgency")
    pdf.body_text(
        "Add free-form urgency signals that indicate a company has an urgent need, e.g., "
        "\"Recent funding round\", \"Leadership change\", \"Regulatory deadline\". Choose AND or OR match condition."
    )
    pdf.add_screenshot("06-icp-step4-urgency.png", "Step 4: Urgency Signals")

    # Step 5: Budget
    pdf.add_page()
    pdf.subsection_title("Step 5: Budget")
    pdf.body_text(
        "Add budget signals indicating financial capacity, e.g., \"Recent fundraise >$10M\", "
        "\"IT budget expansion\", \"New CTO hire\". Choose AND or OR match condition."
    )
    pdf.add_screenshot("07-icp-step5-budget.png", "Step 5: Budget Signals")

    # Step 6: Authority
    pdf.subsection_title("Step 6: Authority")
    pdf.body_text(
        "Specify the job titles you want to reach, e.g., CTO, VP of Engineering, Head of Platform."
    )
    pdf.add_screenshot("08-icp-step6-authority.png", "Step 6: Target Roles")

    # Step 7: Review
    pdf.add_page()
    pdf.subsection_title("Step 7: Review")
    pdf.body_text(
        "A summary of everything you entered, including your chosen Discovery Source and "
        "Sales Navigator URL (if applicable). Scan it to make sure nothing is missing."
    )
    pdf.bullet_list([
        "Click \"Run Pipeline\" to save the ICP and immediately start the lead generation pipeline",
        "Click \"Save Only\" to save the ICP for later and run it another time",
    ])
    pdf.add_screenshot("09-icp-step7-review.png", "Step 7: Review \u2014 Summary with Sales Navigator discovery source")

    # ============================================================
    # 5. LINKEDIN SALES NAVIGATOR INTEGRATION
    # ============================================================
    pdf.add_page()
    pdf.section_title("5. LinkedIn Sales Navigator Integration")

    pdf.subsection_title("What It Is")
    pdf.body_text(
        "qlGen integrates with LinkedIn Sales Navigator through Evaboot, a third-party service "
        "that extracts profile data from your Sales Navigator searches. This lets you combine "
        "LinkedIn's curated B2B database with qlGen's AI-driven qualification pipeline."
    )

    pdf.subsection_title("How It Works")
    pdf.numbered_list([
        "Build a search in Sales Navigator \u2014 apply filters for industry, geography, company size, job titles, seniority",
        "Copy the URL from your Sales Navigator search bar",
        "Paste it into qlGen when creating a new ICP (Step 1: Discovery Source)",
        "qlGen auto-extracts your filters from the URL and pre-fills the ICP wizard",
        "When you run the pipeline, Evaboot asynchronously extracts companies and contacts",
        "qlGen's AI agent then scores, enriches, and qualifies every company through the 5-stage pipeline",
    ])

    pdf.subsection_title("Choosing the Right Mode")
    pdf.simple_table(
        ["Scenario", "Recommended Mode"],
        [
            ["No Sales Navigator account", "qlGen Multi-Source"],
            ["Highly curated Sales Nav search", "Sales Navigator Only"],
            ["Want maximum coverage", "Sales Nav + qlGen (Hybrid)"],
            ["Low Evaboot credits", "qlGen Multi-Source"],
            ["Large search + want to supplement", "Sales Nav + qlGen (Hybrid)"],
        ],
        col_widths=[85, 85],
    )

    pdf.subsection_title("Evaboot Credits")
    pdf.bullet_list([
        "1 credit per profile extracted from a Sales Navigator URL",
        "1 credit per email found for each contact",
        "0.5 credit per email validation",
        "Check your balance on the Discovery Source step or the Dashboard",
        "Minimum 10 credits required to start a Sales Navigator extraction",
        "Maximum credits per run is capped at 500 by default",
        "If credits run out mid-extraction, partial results are still processed",
    ])

    pdf.subsection_title("Troubleshooting")
    pdf.simple_table(
        ["Issue", "Solution"],
        [
            ["\"Evaboot Not Configured\"", "Ask your admin to add EVABOOT_API_KEY to the environment"],
            ["\"Sales Nav Session Expired\"", "Re-link your Sales Navigator account in the Evaboot dashboard"],
            ["\"Insufficient credits\"", "Top up your Evaboot account or switch to qlGen Multi-Source"],
            ["Saved list URL no auto-fill", "Saved lists don't have filter params \u2014 use a search URL or fill manually"],
        ],
        col_widths=[55, 115],
    )

    # ============================================================
    # 6. PIPELINE PROGRESS
    # ============================================================
    pdf.add_page()
    pdf.section_title("6. Pipeline Progress")
    pdf.body_text(
        "After starting a search, the Pipeline Progress page shows the AI agent working in "
        "real time. The pipeline runs through multiple stages:"
    )
    pdf.bullet_list([
        "Industry Discovery \u2014 finds companies matching your ICP criteria",
        "Firmographic Fit \u2014 evaluates company size, revenue, geography match",
        "Review & Select \u2014 you review discovered companies and select which to continue with",
        "Signal Research \u2014 evaluates budget and urgency signals for selected companies",
        "Contact Discovery \u2014 finds decision-makers at each qualified company",
        "Final Ranking \u2014 BANT scoring and final lead qualification",
    ])
    pdf.body_text(
        "A progress bar at the top shows which stages are complete. You can choose how "
        "signal research runs: Both at Once (faster), Budget First, or Urgency First."
    )
    pdf.add_screenshot("11-pipeline-progress.png", "Pipeline Progress \u2014 Review gate with discovered companies and fit scores")

    pdf.body_text(
        "When using Sales Navigator mode, you'll see additional activity: Evaboot credit check, "
        "async extraction, polling for completion, and companies being parsed from LinkedIn data."
    )
    pdf.tip_box(
        "You can safely leave this page. Results are saved automatically. "
        "Come back anytime via the Dashboard."
    )

    # ============================================================
    # 7. VIEWING YOUR RESULTS
    # ============================================================
    pdf.add_page()
    pdf.section_title("7. Viewing Your Results")
    pdf.body_text(
        "When the search completes, the Search Results page has four tabs:"
    )

    pdf.subsection_title("Companies Tab (default)")
    pdf.body_text(
        "A table of all discovered companies with their key metrics:"
    )
    pdf.simple_table(
        ["Column", "What It Shows"],
        [
            ["Company", "The discovered company name"],
            ["Industry", "Company industry classification"],
            ["Country", "Company location"],
            ["Revenue", "Estimated annual revenue"],
            ["Asset Value", "Estimated asset value"],
            ["Final Score", "Lead quality score"],
            ["Budget", "Budget signal score"],
            ["Urgency", "Urgency signal score"],
            ["Contacts", "Number of contacts found"],
        ],
        col_widths=[40, 130],
    )
    pdf.body_text(
        "Click any row to expand it and see Company Insights (ICP match, revenue, employee count, "
        "tech stack) and detailed BANT Breakdown with scores and reasoning."
    )
    pdf.add_screenshot("12-leads-companies.png", "Search Results \u2014 Companies tab with export options")

    pdf.add_page()
    pdf.subsection_title("Pipeline Funnel Tab")
    pdf.body_text(
        "Visual funnel showing how companies progress through each pipeline stage, with counts "
        "at each stage showing how the AI filtered and qualified companies."
    )

    pdf.subsection_title("Search Criteria Tab")
    pdf.body_text(
        "Shows the ICP configuration used for this search, including discovery mode and "
        "Sales Navigator URL if used."
    )

    pdf.subsection_title("Search Summary Tab")
    pdf.body_text(
        "An overview of how the search was conducted: time taken, sources searched, "
        "data completeness metrics, and Evaboot credits consumed (if applicable)."
    )

    pdf.subsection_title("Exporting Results")
    pdf.body_text(
        "On the Companies tab, click \"Export Excel\" for a formatted .xlsx file or use the CSV "
        "dropdown for a CSV export. Files include all companies, contacts, scores, and details "
        "\u2014 ready to import into your CRM."
    )

    # ============================================================
    # 8. BANT SCORES
    # ============================================================
    pdf.add_page()
    pdf.section_title("8. Understanding BANT Scores")
    pdf.body_text("Every company is scored on 4 dimensions, each rated 0\u20135:")
    pdf.simple_table(
        ["Letter", "Dimension", "What It Measures"],
        [
            ["B", "Budget", "Does the company have the financial capacity?"],
            ["A", "Authority", "Did we reach the right decision-maker?"],
            ["N", "Need", "Does the company have a clear need for your offering?"],
            ["T", "Timing", "Is there urgency or a near-term trigger?"],
        ],
        col_widths=[20, 40, 110],
    )
    pdf.body_text("Total score is out of 20. The color-coded labels mean:")
    pdf.simple_table(
        ["Score Range", "Label", "What It Means"],
        [
            ["16\u201320", "HOT", "High-priority lead \u2014 reach out immediately"],
            ["12\u201315", "WARM", "Good potential \u2014 worth pursuing soon"],
            ["9\u201311", "COOL", "Some potential \u2014 may need nurturing"],
            ["0\u20138", "COLD", "Low match \u2014 deprioritize for now"],
        ],
        col_widths=[35, 25, 110],
    )

    # ============================================================
    # 9. MANAGING SAVED ICPS
    # ============================================================
    pdf.add_page()
    pdf.section_title("9. Managing Saved ICPs")
    pdf.body_text("The Saved ICPs page lists all your ICP configurations. From here you can:")
    pdf.bullet_list([
        "Search: Use the search bar to filter by name or description",
        "View Details: Click any card to see the full ICP configuration",
        "Edit: Click the \"Edit\" button or use the \"...\" menu on any card",
        "Run Pipeline: Use the \"...\" menu and select \"Run Pipeline\" to start a new search",
        "Delete: Use the \"...\" menu to delete an ICP you no longer need",
        "Import from Excel: Use the bulk import feature for multiple ICPs",
    ])
    pdf.add_screenshot("10-saved-icps.png", "Saved ICPs page \u2014 search, edit, run, or delete your profiles")

    # ============================================================
    # 10. DASHBOARD
    # ============================================================
    pdf.add_page()
    pdf.section_title("10. Using the Dashboard")

    pdf.subsection_title("Summary Tiles")
    pdf.bullet_list([
        "Total Searches: How many search pipelines you've run",
        "Qualified Leads: Total contacts found across all searches",
        "Companies Found: Total companies discovered",
    ])

    pdf.subsection_title("Evaboot / Sales Navigator Status")
    pdf.body_text(
        "The dashboard shows your Evaboot credit balance, daily extraction limits, Sales Navigator "
        "session status, and your personal usage. Recent Evaboot searches are listed with credits "
        "consumed and companies found. Click the Refresh button for a live quota check."
    )

    pdf.subsection_title("Recent Searches")
    pdf.body_text(
        "Cards showing your latest searches with status badge (Completed, Running, Awaiting Review, "
        "Cancelled, Failed), company/contact counts, ICP details, and discovery mode indicator. "
        "Use the search bar and status filters to find specific searches."
    )
    pdf.add_screenshot("02-dashboard.png", "Dashboard \u2014 summary tiles, Evaboot status, and recent searches")

    pdf.add_page()
    pdf.subsection_title("Admin: Team Activity")
    pdf.body_text(
        "Admins see an additional Team Activity section with aggregate stats: Total Users, "
        "Active Users (7 days), Total ICPs, and Total Searches. Tabs for Users, Searches, "
        "and ICPs provide detailed breakdowns."
    )
    pdf.add_screenshot("02-dashboard-full.png", "Full Dashboard view \u2014 including admin Team Activity section")

    # ============================================================
    # 11. AI CO-PILOT
    # ============================================================
    pdf.add_page()
    pdf.section_title("11. AI Co-pilot")
    pdf.body_text(
        "The qlGen Co-pilot is an AI assistant available on every page. Click the sparkle "
        "button in the bottom-right corner to open the sliding panel."
    )
    pdf.body_text(
        "The Co-pilot is context-aware \u2014 it knows which page you're on and provides relevant "
        "suggestions. On the Dashboard, it offers data overviews, best leads analysis, industry "
        "breakdowns, and geographic distribution insights."
    )
    pdf.subsection_title("What You Can Ask")
    pdf.bullet_list([
        "Ask about your leads, companies, or search results",
        "Get AI-powered research and recommendations",
        "Explore data with semantic search across your companies",
        "Get industry breakdowns and geographic distributions",
        "Find the best leads across all your runs",
    ])
    pdf.add_screenshot("23-copilot-panel.png", "Co-pilot panel \u2014 context-aware suggestions on the Dashboard")

    # ============================================================
    # 12. HELP & FEEDBACK
    # ============================================================
    pdf.add_page()
    pdf.section_title("12. Help & Feedback")
    pdf.body_text(
        "Click the question mark icon (?) in the top-right corner to access the Help menu "
        "with three options:"
    )
    pdf.numbered_list([
        "User Guide \u2014 Opens this PDF documentation",
        "Submit Feedback \u2014 Opens a modal to submit feedback, complaints, bug reports, or feature requests",
        "My Submissions \u2014 View your submitted feedback with status updates and admin replies",
    ])
    pdf.add_screenshot("22-help-menu.png", "Help menu \u2014 User Guide, Submit Feedback, and My Submissions")

    pdf.subsection_title("Submitting Feedback")
    pdf.body_text(
        "When you click \"Submit Feedback\", a modal appears where you can:"
    )
    pdf.bullet_list([
        "Choose a type: Feedback, Complaint, Bug Report, or Feature Request",
        "Enter a subject line",
        "Provide a detailed description",
    ])
    pdf.body_text(
        "After submission, you can track your feedback status (Open, In Progress, Resolved, Closed) "
        "and see admin replies via \"My Submissions\"."
    )

    # ============================================================
    # 13. ADMIN FEATURES
    # ============================================================
    pdf.add_page()
    pdf.section_title("13. Admin Features")
    pdf.body_text("Admin users have access to additional features:")

    pdf.subsection_title("User Management")
    pdf.body_text(
        "The Users page lets admins manage user accounts, view roles (Super Admin, Admin, User), "
        "and monitor activity."
    )
    pdf.add_screenshot("20-users-page.png", "User Management page")

    pdf.subsection_title("Tools Registry")
    pdf.body_text(
        "The Tools page shows all external tools/APIs used by qlGen, their availability status, "
        "and rate limits. Admins can monitor tool health and usage."
    )
    pdf.add_screenshot("18-tools-registry.png", "Tools Registry \u2014 API availability and rate limits")

    pdf.add_page()
    pdf.subsection_title("Feedback Management")
    pdf.body_text(
        "The Feedback page (admin only) shows all user-submitted feedback. Admins can filter "
        "by type and status, update feedback status, and reply to users."
    )
    pdf.add_screenshot("21-feedback-page.png", "Feedback Management \u2014 view, filter, and respond to user feedback")

    pdf.subsection_title("All Leads")
    pdf.body_text(
        "The All Leads page provides a consolidated view of qualified leads across all "
        "search runs, making it easy to find and export the best leads."
    )
    pdf.add_screenshot("17-all-leads.png", "All Leads \u2014 consolidated view across all searches")

    # ============================================================
    # 14. BULK IMPORT
    # ============================================================
    pdf.add_page()
    pdf.section_title("14. Bulk Import: Multiple ICPs from Excel")
    pdf.body_text("If you need to create several ICPs at once:")
    pdf.numbered_list([
        "Go to the Saved ICPs page",
        "Click \"Import from Excel\", or use the import option in the ICP wizard",
        "Download the template \u2014 it has sheets matching the ICP dimensions",
        "Fill in your data. Use the \"ICP Name\" column to define multiple ICPs",
        "Upload the completed .xlsx file",
        "Review the parsed ICPs and click \"Save All\" or \"Save & Run All\"",
    ])

    # ============================================================
    # 15. TIPS
    # ============================================================
    pdf.section_title("15. Tips for Better Results")
    pdf.numbered_list([
        "Be specific with your ICP: The more detail you provide (industries, regions, company size, signals), the more targeted the results.",
        "Use multiple target roles: Adding 3\u20135 leadership roles increases the chance of finding the right decision-maker.",
        "Start from Sales Navigator when possible: Pasting a well-filtered search URL with Hybrid mode gives you LinkedIn's precision plus qlGen's depth.",
        "Use \"Fill remaining with AI\": After pasting a Sales Navigator URL, click this to have AI complete urgency signals, budget signals, and other fields.",
        "Review and re-run: After seeing initial results, edit your ICP to refine criteria and run a new search.",
        "Export early, export often: Download the Excel file to share with your team or import into your CRM.",
        "Focus on HOT and WARM leads first: Sort by final score and prioritize the top-scoring companies.",
        "Monitor Evaboot credits: Check the Dashboard regularly. Narrow your Sales Navigator search to control credit usage.",
    ])

    # ============================================================
    # 16. FAQ
    # ============================================================
    pdf.add_page()
    pdf.section_title("16. Frequently Asked Questions")

    faqs = [
        ("How long does a search take?",
         "Typically 3\u20138 minutes depending on the breadth of your ICP criteria. Sales Navigator extractions may add 1\u20133 minutes."),
        ("Can I leave the page while a search is running?",
         "Yes. Results are saved automatically. You can close the tab entirely and come back later via the Dashboard."),
        ("How many companies does each search find?",
         "Each search is configured to find up to 15 companies with up to 5 contacts per company."),
        ("Can I run the same ICP multiple times?",
         "Yes. Each run is independent. Re-run from Saved ICPs, Dashboard, or the \"Run Again\" button on results."),
        ("What data sources does qlGen use?",
         "Apollo.io, Exa.ai, Hunter.io, Lusha, Tavily, DuckDuckGo, direct website analysis, and LinkedIn Sales Navigator (via Evaboot)."),
        ("Can I edit an ICP after saving it?",
         "Yes. Go to Saved ICPs, click the card, and choose \"Edit\". Changes don't affect previous results."),
        ("What format is the export?",
         "Excel (.xlsx) with formatted columns and styling, or CSV. Ready for direct use or CRM import."),
        ("Do I need a Sales Navigator account?",
         "No. Sales Navigator is optional. The default qlGen Multi-Source mode works without LinkedIn access."),
        ("What happens if Evaboot extraction fails?",
         "In Sales Navigator Only mode, the pipeline stops with an error. In Hybrid mode, it gracefully continues using qlGen's standard discovery."),
        ("How do I connect my Sales Navigator account?",
         "Sales Navigator is connected through Evaboot. Your admin configures the API key, and you link your account in the Evaboot dashboard."),
        ("How do I submit feedback or report a bug?",
         "Click the question mark (?) icon in the top-right corner and select \"Submit Feedback\". Choose the appropriate type and provide details."),
    ]

    for q, a in faqs:
        pdf.set_font("Inter", "B", 10)
        pdf.set_text_color(*UserGuidePDF.DARK)
        pdf.multi_cell(0, 6, f"Q: {q}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Inter", "", 10)
        pdf.set_text_color(*UserGuidePDF.GRAY)
        pdf.multi_cell(0, 6, f"A: {a}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # Final note
    pdf.ln(6)
    pdf.set_draw_color(*UserGuidePDF.PURPLE)
    pdf.set_line_width(0.5)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(6)
    pdf.set_font("Inter", "I", 10)
    pdf.set_text_color(*UserGuidePDF.GRAY)
    pdf.cell(0, 6, "For technical support or questions, contact your system administrator.", align="C")

    # Save
    pdf.output(OUTPUT_PDF)
    print(f"PDF generated successfully: {OUTPUT_PDF}")
    print(f"Total pages: {pdf.page_no()}")


if __name__ == "__main__":
    generate_guide()
