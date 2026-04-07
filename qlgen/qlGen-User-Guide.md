# qlGen User Guide

**AI-Powered Qualified Lead Generation**

---

## What is qlGen?

qlGen helps you build a pipeline of qualified leads in minutes. You define your Ideal Customer Profile (ICP) — the type of company and decision-maker you want to sell to — and qlGen's AI agent automatically:

1. **Discovers companies** matching your criteria (via web sources or LinkedIn Sales Navigator)
2. **Finds key contacts** (decision-makers) at each company
3. **Enriches contact details** — emails, phone numbers, LinkedIn profiles
4. **Scores every lead** using the BANT framework (Budget, Authority, Need, Timing)

The result is a sales-ready list you can export to Excel and start working immediately.

---

## Navigation

The top navigation bar has these sections:

| Menu Item      | What It Does                                       |
|----------------|-----------------------------------------------------|
| **Home**       | Landing page with quick-start buttons               |
| **Dashboard**  | Overview of all your searches, aggregate stats, and Evaboot credit balance |
| **All Leads**  | View qualified leads across all searches             |
| **Saved ICPs** | Your saved Ideal Customer Profiles (reusable)        |
| **Tools**      | Tool availability and rate limits (admin only)       |
| **Users**      | User management (admin only)                         |
| **Feedback**   | Feedback management (admin only)                     |

---

## Getting Started: Your First Search

### Step 1 — Create a New Search

From the **Home** page, click **"Start Your Search"**. This opens the ICP Configuration wizard.

Alternatively, you can click **"New Search"** from the **Dashboard** or the **Saved ICPs** page.

### Step 2 — Fill in the 7-Step ICP Wizard

The wizard walks you through defining your ideal customer. Each step captures a different dimension. You can navigate between steps freely by clicking the step numbers on the left sidebar.

#### Step 1: Discovery Source

Choose how companies should be discovered. This controls **Stage 1 (Industry Discovery)** and **Stage 2 (Firmographic Fit)**. Stages 3–5 (Signals, Contacts, Scoring) run the same regardless of your choice.

| Mode | Description | Credits |
|------|-------------|---------|
| **qlGen Multi-Source** | Uses Apollo, Exa, DuckDuckGo, registries, and more. No extra credits needed. This is the default. | Free |
| **Sales Navigator Only** | Extracts companies and contacts directly from your LinkedIn Sales Navigator search via Evaboot. Pipeline fails if extraction fails. | 1 credit/profile |
| **Sales Navigator + qlGen (Hybrid)** | LinkedIn Sales Navigator data combined with qlGen's multi-source discovery for maximum coverage. Falls back to qlGen-only if extraction fails. | 1 credit/profile |

**If you select a Sales Navigator mode:**

1. **Evaboot Account Status** is displayed automatically, showing:
   - **Credits Available** — your remaining Evaboot credits
   - **Daily Usage** — how many credits you've used today vs. your daily limit
   - **Sales Nav Session** — whether your LinkedIn Sales Navigator cookie is connected (must show "Connected")

2. **Paste your Sales Navigator URL** — copy the URL from your LinkedIn Sales Navigator search bar and paste it into the input field. Both search URLs and saved list URLs are supported.

3. **Auto-fill from URL** — if you paste a search URL (not a saved list), qlGen automatically extracts filters from the URL and pre-fills your ICP fields:
   - Industry types
   - Geography / countries
   - Employee range
   - Revenue range
   - Target roles (from title and seniority filters)
   - Offerings (from function and keyword filters)
   - A descriptive name is also auto-generated (e.g., *"Software & SaaS - US & UK - 100-500 emp"*)

   After auto-fill, you'll see a green summary box showing which filters were extracted and which fields still need your input (e.g., Urgency Signals, Budget Signals).

4. **"Fill remaining with AI"** — click this button to have AI generate the missing fields (urgency signals, budget signals, etc.) based on the Sales Navigator search context. This is the fastest way to complete your ICP when starting from a Sales Navigator URL.

> **Tip:** Narrow your search in Sales Navigator first to control Evaboot credit usage. The more targeted your Sales Navigator search, the fewer credits consumed.

> **Note:** Saved list URLs don't contain filter parameters to extract, so auto-fill won't work. Use the AI generation or fill fields manually.

#### Step 2: Firmographics

This step combines your company targeting criteria. When using Sales Navigator mode, an info banner reminds you that discovery is handled by your Sales Nav URL — these criteria are used by the AI agent to **score** each company's fit.

- **Name** (required): Give this search a descriptive name, e.g., *"MidMarket US ECommerce Q1 2026"*
- **Description**: Optional short summary
- **Industry Verticals**: Add one or more industry verticals (e.g., *E-Commerce*) with optional sub-verticals (e.g., *Fashion & Apparel*). Click **"+ Add Industry"** for more rows.
- **Target Countries**: e.g., *United States, United Kingdom*
- **Employee Count Range**: Min and max headcount
- **Revenue Range**: Currency, min, and max revenue
- **Low Cost Center**: Toggle on if targeting companies with low-cost center operations

> **Tip:** If you have ICP data in a spreadsheet, click **"Create with AI / Upload"** at the top of this step to pre-fill the wizard. You can describe your ideal customer in plain English or upload a file (PDF, DOCX, XLSX, TXT, CSV).

#### Step 3: Capability

- **Target Offerings / Service Areas**: The products or services you want to sell. Press Enter or click "Add" after typing each one.
- **Match Condition**: Choose **AND** (company must match ALL offerings) or **OR** (company must match ANY offering).

#### Step 4: Urgency

- **Urgency Signals**: Free-form signals that indicate a company has an urgent need, e.g., *"Recent funding round"*, *"Leadership change"*, *"Regulatory deadline"*
- **Match Condition**: AND or OR

#### Step 5: Budget

- **Budget Signals**: Free-form signals that indicate budget availability, e.g., *"Recent fundraise >$10M"*, *"IT budget expansion"*, *"New CTO hire"*
- **Match Condition**: AND or OR

#### Step 6: Authority

- **Target Roles**: Job titles you want to reach, e.g., *CTO, VP of Engineering, Head of Platform*

#### Step 7: Review

A summary of everything you entered, including your chosen Discovery Source and Sales Navigator URL (if applicable). Scan it to make sure nothing is missing.

- Click **"Save & Run Search"** to save the ICP and immediately start the lead generation pipeline.
- Click **"Save Only"** if you want to save the ICP for later and run it another time.

### Step 3 — Watch the Pipeline Run

After clicking **"Save & Run Search"**, you are taken to the **Pipeline Progress** page. Here you can see the AI agent working in real time:

- **Left panel**: Shows the stages — Company Discovery, Contact Discovery, Enrichment, BANT Scoring — with progress indicators
- **Right panel**: A live activity log showing every data source lookup as it happens
- **Bottom bar**: Running totals of companies found, contacts found, tool calls, and elapsed time

**When using Sales Navigator mode**, you'll see additional activity in Stage 1:
- Evaboot credit check
- Async extraction from your Sales Navigator URL (may take a few minutes)
- Polling for extraction completion
- Companies and contacts being parsed from LinkedIn data

> **You can safely leave this page.** Results are saved automatically. Come back anytime via the Dashboard.

A typical search runs for **3-8 minutes** depending on how many companies match your criteria. Sales Navigator extractions may add 1-3 minutes for the LinkedIn data extraction.

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
Shows the ICP configuration that was used for this search, including the discovery mode and Sales Navigator URL if used.

#### Search Summary Tab
An overview of how the search was conducted:
- Time taken, sources searched, total lookups
- Which data sources contributed (with bar charts)
- Data completeness metrics (% of contacts with email, phone, LinkedIn)
- Evaboot credits consumed (if Sales Navigator mode was used)

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

### Evaboot Status (if configured)
The dashboard shows your Evaboot credit balance, daily limits, and recent Sales Navigator pipeline runs with credits consumed. Click the refresh button for a live quota check.

### Recent Searches
Cards showing your latest searches with:
- Status badge (Completed, Running, Failed)
- Company and contact counts
- ICP details (regions, industries, roles)
- Discovery mode indicator (qlGen, Sales Navigator, or Hybrid)
- Quick actions: Edit the ICP, delete the search, or view results

Use the **search bar** and **status filters** (All, Completed, Running, Failed) to find specific searches.

---

## LinkedIn Sales Navigator Integration

### What It Is

qlGen integrates with LinkedIn Sales Navigator through Evaboot, a third-party service that extracts profile data from your Sales Navigator searches. This lets you combine LinkedIn's curated B2B database with qlGen's AI-driven qualification pipeline.

### How It Works

1. **You build a search in Sales Navigator** — apply filters for industry, geography, company size, job titles, seniority, etc.
2. **Copy the URL** from your Sales Navigator search bar
3. **Paste it into qlGen** when creating a new ICP (Step 1: Discovery Source)
4. **qlGen auto-extracts your filters** from the URL and pre-fills the ICP wizard
5. **When you run the pipeline**, Evaboot asynchronously extracts companies and contacts from your Sales Navigator search
6. **qlGen's AI agent** then scores, enriches, and qualifies every company through the standard 5-stage pipeline

### Choosing the Right Mode

| Scenario | Recommended Mode |
|----------|-----------------|
| No Sales Navigator account | **qlGen Multi-Source** |
| Highly curated Sales Nav search, trust the results | **Sales Navigator Only** |
| Want maximum coverage from all sources | **Sales Navigator + qlGen (Hybrid)** |
| Low Evaboot credits, want to conserve | **qlGen Multi-Source** |
| Large Sales Nav search + want to supplement gaps | **Sales Navigator + qlGen (Hybrid)** |

### Evaboot Credits

- **1 credit per profile** extracted from a Sales Navigator URL
- **Email enrichment** costs additional credits if enabled
- Check your balance on the **Discovery Source** step or the **Dashboard**
- A minimum of **10 credits** is required to start a Sales Navigator extraction
- Maximum credits per run is capped at **500** by default
- If credits run out mid-extraction, partial results are still processed

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "Evaboot Not Configured" | Ask your admin to add `EVABOOT_API_KEY` to the environment |
| "Sales Navigator Session Expired" | Re-link your Sales Navigator account in the Evaboot dashboard |
| "Insufficient credits" | Top up your Evaboot account or switch to qlGen Multi-Source mode |
| Saved list URL doesn't auto-fill | Saved lists don't contain filter parameters — use a search URL instead, or fill fields manually |

---

## Bulk Import: Multiple ICPs from Excel

If you need to create several ICPs at once:

1. Go to **Saved ICPs** page
2. When the page is empty, click **"Import from Excel"**, or use the import option in the ICP wizard
3. **Download the template** — it has sheets matching the ICP dimensions
4. Fill in your data. Use the "ICP Name" column to define multiple ICPs in the same file
5. Upload the completed `.xlsx` file
6. Review the parsed ICPs and click **"Save All"** or **"Save & Run All"**

---

## Tips for Better Results

1. **Be specific with your ICP**: The more detail you provide (industries, regions, company size, urgency and budget signals), the more targeted and useful the results will be.

2. **Use multiple target roles**: Adding 3-5 leadership roles (e.g., CTO, VP Engineering, Head of Platform) increases the chance of finding the right decision-maker at each company.

3. **Start from Sales Navigator when possible**: If you have a Sales Navigator account, pasting a well-filtered search URL and using the Hybrid mode gives you the best of both worlds — LinkedIn's precision plus qlGen's depth.

4. **Use "Fill remaining with AI"**: After pasting a Sales Navigator URL, click this button to have AI complete the urgency signals, budget signals, and other fields automatically. This is the fastest way to go from a Sales Navigator search to a fully qualified lead list.

5. **Review and re-run**: After seeing initial results, you can edit your ICP to refine criteria and run a new search. Each run is independent.

6. **Export early, export often**: Download the Excel file to share with your team or import into your CRM. You can re-export anytime.

7. **Focus on HOT and WARM leads first**: Sort by BANT score (default) and prioritize the top-scoring companies for outreach.

8. **Monitor Evaboot credits**: Check the Dashboard regularly if you're running Sales Navigator searches. Narrow your Sales Navigator search before pasting the URL to control how many profiles are extracted.

---

## AI Co-pilot

The qlGen Co-pilot is an AI assistant available on every page. Click the sparkle button in the bottom-right corner to open the sliding panel.

The Co-pilot is context-aware — it knows which page you're on and provides relevant suggestions. On the Dashboard, it offers data overviews, best leads analysis, industry breakdowns, and geographic distribution insights.

### What You Can Ask

- Ask about your leads, companies, or search results
- Get AI-powered research and recommendations
- Explore data with semantic search across your companies
- Get industry breakdowns and geographic distributions
- Find the best leads across all your runs

---

## Help & Feedback

Click the question mark icon (?) in the top-right corner to access the Help menu with three options:

1. **User Guide** — Opens this PDF documentation
2. **Submit Feedback** — Opens a modal to submit feedback, complaints, bug reports, or feature requests
3. **My Submissions** — View your submitted feedback with status updates and admin replies

### Submitting Feedback

When you click "Submit Feedback", a modal appears where you can:

- Choose a type: **Feedback**, **Complaint**, **Bug Report**, or **Feature Request**
- Enter a subject line
- Provide a detailed description

After submission, you can track your feedback status (Open, In Progress, Resolved, Closed) and see admin replies via "My Submissions".

### Admin Feedback Management

Admins can access the **Feedback** page from the navigation bar to:

- View all user-submitted feedback
- Filter by type and status
- Update feedback status
- Reply to users

---

## Admin Features

### User Management

The **Users** page lets admins manage user accounts, view roles (Super Admin, Admin, User), and monitor activity.

### Tools Registry

The **Tools** page shows all external tools/APIs used by qlGen, their availability status, and rate limits. Admins can monitor tool health and usage.

### All Leads

The **All Leads** page provides a consolidated view of qualified leads across all search runs, making it easy to find and export the best leads.

---

## Frequently Asked Questions

**Q: How long does a search take?**
Typically 3-8 minutes depending on the breadth of your ICP criteria and how many companies are found. Sales Navigator extractions may add 1-3 minutes.

**Q: Can I leave the page while a search is running?**
Yes. Results are saved automatically. You can close the tab entirely and come back later via the Dashboard.

**Q: How many companies does each search find?**
Each search is configured to find up to 15 companies with up to 5 contacts per company. These are the most relevant matches for your criteria.

**Q: Can I run the same ICP multiple times?**
Yes. Each run is independent. You can re-run from the Saved ICPs page, the Dashboard card, or the "Run Again" button on the results page.

**Q: What data sources does qlGen use?**
qlGen searches across multiple professional data sources including Apollo.io, Exa.ai, Hunter.io, Lusha, Tavily, DuckDuckGo, direct company website analysis, and LinkedIn Sales Navigator (via Evaboot).

**Q: Can I edit an ICP after saving it?**
Yes. Go to Saved ICPs, click the card, and choose "Edit". Changes are saved without affecting previous search results.

**Q: What format is the export?**
Excel (.xlsx) with formatted columns and styling, ready for direct use or CRM import.

**Q: Do I need a Sales Navigator account?**
No. Sales Navigator is optional. The default **qlGen Multi-Source** mode discovers companies using web sources, databases, and APIs without requiring LinkedIn access.

**Q: What happens if Evaboot extraction fails?**
In **Sales Navigator Only** mode, the pipeline will stop with an error. In **Hybrid** mode, the pipeline gracefully continues using qlGen's standard multi-source discovery.

**Q: How do I connect my Sales Navigator account?**
Sales Navigator is connected through Evaboot. Your admin needs to configure the Evaboot API key, and you need to link your Sales Navigator account in the Evaboot dashboard.

**Q: How do I submit feedback or report a bug?**
Click the question mark (?) icon in the top-right corner and select "Submit Feedback". Choose the appropriate type (Feedback, Complaint, Bug Report, or Feature Request) and provide details.

**Q: What is the AI Co-pilot?**
The Co-pilot is a context-aware AI assistant available on every page. Click the sparkle button in the bottom-right corner to ask questions about your leads, get research recommendations, or explore your data.

---

*For technical support or questions, contact your system administrator.*
