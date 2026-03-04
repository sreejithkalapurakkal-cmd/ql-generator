# qlGen User Guide

**AI-Powered Qualified Lead Generation**

---

## What is qlGen?

qlGen helps you build a pipeline of qualified leads in minutes. You define your Ideal Customer Profile (ICP) — the type of company and decision-maker you want to sell to — and qlGen's AI agent automatically:

1. **Discovers companies** matching your criteria
2. **Finds key contacts** (decision-makers) at each company
3. **Enriches contact details** — emails, phone numbers, LinkedIn profiles
4. **Scores every lead** using the BANT framework (Budget, Authority, Need, Timing)

The result is a sales-ready list you can export to Excel and start working immediately.

---

## Navigation

The top navigation bar has three sections:

| Menu Item      | What It Does                                       |
|----------------|-----------------------------------------------------|
| **Home**       | Landing page with quick-start buttons               |
| **Dashboard**  | Overview of all your searches and aggregate stats    |
| **Saved ICPs** | Your saved Ideal Customer Profiles (reusable)        |

---

## Getting Started: Your First Search

### Step 1 — Create a New Search

From the **Home** page, click **"Start Your Search"**. This opens the ICP Configuration wizard.

Alternatively, you can click **"New Search"** from the **Dashboard** or the **Saved ICPs** page.

### Step 2 — Fill in the 9-Step ICP Wizard

The wizard walks you through defining your ideal customer. Each step captures a different dimension. You can navigate between steps freely by clicking the step numbers on the left sidebar.

#### Step 1: Offering
- **Name** (required): Give this search a descriptive name, e.g., *"MidMarket US ECommerce Q1 2026"*
- **Description**: Optional short summary
- **Target Offerings / Service Areas**: The products or services you want to sell. Press Enter or click "Add" after typing each one.

> **Tip:** If you have ICP data in a spreadsheet, click **"Import from Excel"** at the top of this step to pre-fill the wizard. You can download a template first.

#### Step 2: Regions
- **Target Countries**: e.g., *United States, United Kingdom*
- **Priority Areas**: Specific states or cities, e.g., *California, New York, London*

#### Step 3: Industry
- Add one or more industry verticals (e.g., *E-Commerce*) with optional sub-verticals (e.g., *Fashion & Apparel*)
- Click **"+ Add Industry"** to add more rows

#### Step 4: Size
- **Employee count range**: Min and max headcount
- **Revenue range**: Currency, min, and max revenue

#### Step 5: Tech (Technology Maturity)
- **Positive signals**: Technologies that indicate a good fit, e.g., *"Running on Shopify Plus"*
- **Negative signals**: Migration needs or outdated tech, e.g., *"Legacy Magento 1"*

#### Step 6: Infra (Infrastructure Readiness)
- Indicators that the company is technically ready, e.g., *"Cloud-hosted storefront"*

#### Step 7: Drivers (Digital Transformation Drivers)
- **Growth Triggers**: e.g., *"YoY revenue growth >20%"*
- **Operational Pains**: e.g., *"Site performance degrading during peak traffic"*
- **Competitive Pressures**: e.g., *"Rising customer acquisition cost"*
- **Strategic Initiatives**: e.g., *"Launching mobile app"*

#### Step 8: Leadership
- **Target Roles**: Job titles you want to reach, e.g., *CTO, VP of Engineering, Head of Digital*
- **Behavioral Traits**: e.g., *"Data-driven decision maker"*

#### Step 9: Review
- A summary of everything you entered. Scan it to make sure nothing is missing.
- Click **"Save & Run Search"** to save the ICP and immediately start the lead generation pipeline.
- Click **"Save Only"** if you want to save the ICP for later and run it another time.

### Step 3 — Watch the Pipeline Run

After clicking **"Save & Run Search"**, you are taken to the **Pipeline Progress** page. Here you can see the AI agent working in real time:

- **Left panel**: Shows the 4 stages — Company Discovery, Contact Discovery, Enrichment, BANT Scoring — with progress indicators
- **Right panel**: A live activity log showing every data source lookup as it happens
- **Bottom bar**: Running totals of companies found, contacts found, tool calls, and elapsed time

> **You can safely leave this page.** Results are saved automatically. Come back anytime via the Dashboard.

A typical search runs for **3-8 minutes** depending on how many companies match your criteria.

### Step 4 — View Your Results

When the search completes, click **"View Leads"** (or find the search on your Dashboard and click it).

The **Search Results** page has three tabs:

#### Companies Tab (default)
A table of all discovered companies and their contacts:

| Column        | What It Shows                                                |
|---------------|--------------------------------------------------------------|
| #             | Row number                                                   |
| Company Name  | The discovered company                                       |
| BANT Score    | Lead quality rating (HOT / WARM / COOL / COLD) out of 20    |
| Website       | Company website (clickable link)                             |
| Geo/City      | Location                                                     |
| Contact Name  | Decision-maker's name                                        |
| Designation   | Job title                                                    |
| LinkedIn      | Link to their LinkedIn profile                               |
| Email         | Professional email address                                   |
| Phone         | Phone number                                                 |

**Click any row to expand it** and see:
- **Company Insights**: ICP match score, estimated revenue, employee count, tech stack, and an overview of why this company was matched
- **BANT Breakdown**: Detailed scores and reasoning for Budget, Authority, Need, and Timing, with source citations

#### Search Criteria Tab
Shows the ICP configuration that was used for this search.

#### Search Summary Tab
An overview of how the search was conducted:
- Time taken, sources searched, total lookups
- Which data sources contributed (with bar charts)
- Data completeness metrics (% of contacts with email, phone, LinkedIn)

### Step 5 — Export to Excel

On the Companies tab, click **"Export Excel"** in the top right. This downloads a formatted `.xlsx` file with all companies, contacts, BANT scores, and details — ready to import into your CRM or share with your team.

---

## Understanding BANT Scores

Every company is scored on 4 dimensions, each rated 0-5:

| Letter | Dimension     | What It Measures                                          |
|--------|---------------|-----------------------------------------------------------|
| **B**  | Budget        | Does the company have the financial capacity?             |
| **A**  | Authority     | Did we reach the right decision-maker?                    |
| **N**  | Need          | Does the company have a clear need for your offering?     |
| **T**  | Timing        | Is there urgency or a near-term trigger?                  |

**Total score is out of 20.** The color-coded labels mean:

| Score Range | Label    | What It Means                                |
|-------------|----------|----------------------------------------------|
| 16-20       | **HOT**  | High-priority lead — reach out immediately   |
| 12-15       | **WARM** | Good potential — worth pursuing soon          |
| 9-11        | **COOL** | Some potential — may need nurturing           |
| 0-8         | **COLD** | Low match — deprioritize for now              |

---

## Managing Your Saved ICPs

The **Saved ICPs** page lists all your ICP configurations. From here you can:

- **Search**: Use the search bar to filter by name or description
- **View Details**: Click any card to see the full ICP configuration
- **Edit**: Click the **"Edit"** button or use the **"..."** menu on any card
- **Run Pipeline**: Use the **"..."** menu and select **"Run Pipeline"** to start a new search with an existing ICP
- **Delete**: Use the **"..."** menu to delete an ICP you no longer need
- **Import from Excel**: If you have multiple ICPs to create, use the bulk import feature on the empty state

---

## Using the Dashboard

The **Dashboard** gives you a bird's-eye view:

### Summary Tiles
- **Total Searches**: How many search pipelines you've run (click to see a list)
- **Qualified Leads**: Total contacts found across all searches (click to see per-ICP breakdown)
- **Companies Found**: Total companies discovered (click to see per-ICP breakdown)

### Recent Searches
Cards showing your latest searches with:
- Status badge (Completed, Running, Failed)
- Company and contact counts
- ICP details (regions, industries, roles)
- Quick actions: Edit the ICP, delete the search, or view results

Use the **search bar** and **status filters** (All, Completed, Running, Failed) to find specific searches.

---

## Bulk Import: Multiple ICPs from Excel

If you need to create several ICPs at once:

1. Go to **Saved ICPs** page
2. When the page is empty, click **"Import from Excel"**, or use the import option in the ICP wizard
3. **Download the template** — it has 8 sheets matching the 8 ICP dimensions
4. Fill in your data. Use the "ICP Name" column to define multiple ICPs in the same file
5. Upload the completed `.xlsx` file
6. Review the parsed ICPs and click **"Save All"** or **"Save & Run All"**

---

## Tips for Better Results

1. **Be specific with your ICP**: The more detail you provide (industries, regions, company size, tech signals), the more targeted and useful the results will be.

2. **Use multiple target roles**: Adding 3-5 leadership roles (e.g., CTO, VP Engineering, Head of Digital) increases the chance of finding the right decision-maker at each company.

3. **Add technology signals**: If your offering relates to specific tech stacks, mentioning them helps the AI find companies with relevant infrastructure.

4. **Review and re-run**: After seeing initial results, you can edit your ICP to refine criteria and run a new search. Each run is independent.

5. **Export early, export often**: Download the Excel file to share with your team or import into your CRM. You can re-export anytime.

6. **Focus on HOT and WARM leads first**: Sort by BANT score (default) and prioritize the top-scoring companies for outreach.

---

## Frequently Asked Questions

**Q: How long does a search take?**
Typically 3-8 minutes depending on the breadth of your ICP criteria and how many companies are found.

**Q: Can I leave the page while a search is running?**
Yes. Results are saved automatically. You can close the tab entirely and come back later via the Dashboard.

**Q: How many companies does each search find?**
Each search is configured to find up to 15 companies with up to 5 contacts per company. These are the most relevant matches for your criteria.

**Q: Can I run the same ICP multiple times?**
Yes. Each run is independent. You can re-run from the Saved ICPs page, the Dashboard card, or the "Run Again" button on the results page.

**Q: What data sources does qlGen use?**
qlGen searches across 7 professional data sources: Apollo.io, Exa.ai, Hunter.io, Lusha, Tavily, DuckDuckGo, and direct company website analysis.

**Q: Can I edit an ICP after saving it?**
Yes. Go to Saved ICPs, click the card, and choose "Edit". Changes are saved without affecting previous search results.

**Q: What format is the export?**
Excel (.xlsx) with formatted columns and styling, ready for direct use or CRM import.

---

*For technical support or questions, contact your system administrator.*
