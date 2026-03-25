# qlGen — What's New

*March 2026 Release*

---

## 1. Role-Based Access Control (RBAC)

qlGen now supports three distinct user roles with different levels of access, ensuring the right people have the right visibility and control.

| Capability | User | Admin | Super Admin |
|---|---|---|---|
| Create & manage own ICPs | Yes | Yes | Yes |
| Run pipelines on own ICPs | Yes | Yes | Yes |
| View own leads & results | Yes | Yes | Yes |
| View all users' data (read-only) | No | Yes | Yes |
| User activity monitoring | No | Yes | Yes |
| Manage users (invite, deactivate, delete) | No | No | Yes |
| Tool effectiveness dashboard | No | No | Yes |
| Audit logs | No | No | Yes |

**How it works:**

- **User** — Standard access. Can create ICPs, run searches, and view their own results. Data from other users is not visible.
- **Admin** — Read-only oversight across the organization. Can see all users' ICPs, pipeline runs, and results but cannot edit or delete another user's data. Has access to the user activity dashboard.
- **Super Admin** — Full system control. Can invite and manage users, assign roles, activate/deactivate accounts, access audit logs, and manage the tool registry.

**Data isolation** is enforced at every level — a regular user will never see another user's ICPs, searches, or lead data. Admins gain visibility for oversight purposes but cannot modify data they don't own.

**Authentication** is handled via Google OAuth. The first user to sign in is automatically assigned the Super Admin role. All subsequent users must be invited by a Super Admin before they can access the system. Only email addresses from your organization's domain (configurable) are allowed.

---

## 2. User Management (Super Admin)

Super Admins now have a dedicated **User Management** page accessible from the sidebar navigation.

**What you can do:**

- **Invite new users** — Add team members by email. Assign them a role (User, Admin, or Super Admin) at the time of invitation. Only users from the allowed email domain can be invited.
- **Change roles** — Promote a User to Admin, or grant Super Admin access. Role changes take effect immediately.
- **Deactivate accounts** — Toggle a user's active status. Deactivated users are immediately locked out and cannot sign in until reactivated.
- **Delete users** — Permanently remove a user account (Super Admins cannot delete their own account as a safety measure).

The user table displays each person's name, email, profile picture, role, active status, and last login time.

---

## 3. ICP Clone

You can now **duplicate any existing ICP configuration** with a single click, making it faster to create variations of a search criteria without rebuilding from scratch.

**How to use it:**

1. Go to your **Saved ICPs** page
2. Click the menu (three dots) on any ICP card
3. Select **Clone**
4. qlGen creates a copy named "Copy of [Original Name]" and opens it at the **Review** step
5. Modify any fields you want to change (industry, geography, revenue range, signals, etc.)
6. Save or immediately run a pipeline

**What gets copied:** Everything — firmographic details (industry, geography, revenue range, employee range), target capabilities, urgency signals, budget signals, and authority roles. The clone is a completely independent record; changes to it do not affect the original.

---

## 4. Centralized Leads Database

A new **All Leads** page provides a unified view of every qualified company discovered across all your pipeline runs — no more switching between individual search results to find a company.

**Key capabilities:**

- **Cross-run browsing** — See companies from every completed search in a single, sortable table. Each row shows which ICP profile (search criteria) originally found the company.
- **Search** — Free-text search across company names and website domains.
- **Filter by Industry** — Dropdown populated with all industries found across your searches.
- **Filter by Country** — Dropdown populated with all countries found across your searches.
- **Sort options** — Sort by Final Score (default), Budget Signal Score, Urgency Signal Score, Company Name, or Date Added.
- **Pagination** — Server-side pagination (50 companies per page by default) for fast loading even with thousands of results.

**Table columns:** Company Name, Industry, Country, Revenue, Final Score, Budget Signal Score, Urgency Signal Score, Contact Count, and Search Criteria (the ICP name that found this company).

Scores are color-coded: green (70+), amber (40–69), red (below 40) for quick visual scanning.

Click any company row to navigate to its full detail page within the context of the original pipeline run.

**Access from the Dashboard:** The stats panel on the Dashboard now links directly to the All Leads page, so you can jump to your full lead database from the home screen.

---

## 5. Pipeline Funnel View Enhancements

The pipeline results page now includes a dedicated **Pipeline Funnel** tab that visualizes how companies flow through each stage of the search and qualification process.

**6-stage funnel visualization:**

| Stage | What It Does |
|---|---|
| 1. Industry Discovery | Finds companies matching your industry and geography criteria |
| 2. Firmographic Fit | Validates company size, revenue, and other firmographic parameters |
| 3. Budget Signals | Researches financial indicators — funding rounds, revenue growth, IT spending |
| 4. Urgency Signals | Detects time-sensitive triggers — hiring sprees, tech adoption, expansion plans |
| 5. Contact Discovery | Finds decision-makers matching your target roles |
| 6. Final Scoring | Ranks and qualifies leads based on all gathered signals |

**What you see for each stage:**

- **Pass rate** — Percentage of companies that made it through, color-coded (green/amber/red)
- **Status pills** — Counts of companies that passed, failed, were promoted, or excluded
- **Progress bar** — Visual bar showing pass/fail ratio
- **Drop-off indicators** — Between each stage, see how many companies continued vs. dropped off, with the continuation rate as a percentage

**Interactive drill-down:** Click any stage row to expand it and see the individual companies at that stage, including the AI's reasoning for why each company passed or failed, the evidence it found, and the score it assigned.

**Summary header** at the top shows: total companies discovered, total qualified, overall conversion rate, and count of cached (reused) companies from previous runs.

---

## 6. Improved Search Results Experience

The final results page for each pipeline run has been reorganized into a **tabbed layout** for easier navigation:

**Companies tab** (default view):
- Results table with columns: Company, Industry, Country, Revenue, Asset Value, Final Score, Budget Signal Score, Urgency Signal Score, and Contact Count
- **Summary bar** at the top showing: total companies, total contacts, average final score, and score distribution (high/medium/low breakdown)
- **Sort by** Final Score, Budget Score, Urgency Score, Qualification Category, or Company Name
- **Filter views** for multi-step runs: Promoted Only, All Discovered, or Skipped
- **Export options** — Download as CSV or styled Excel (XLSX), with the option to export all companies or only the final qualified set

**Pipeline Funnel tab:**
- Full stage-by-stage breakdown (as described above)

**Search Criteria tab:**
- Displays the exact ICP configuration used for this search — industries, countries, employee range, revenue range, offerings, signals, and target roles

**Search Summary tab:**
- **Data source attribution** — Which tools contributed data (Apollo, Exa, Tavily, Hunter, Lusha, etc.) with tool-specific icons
- **Pipeline execution metrics** — Total time taken, number of sources searched, lookups performed, and percentage of companies scored
- **Data completeness** — Percentage of companies with contacts, contacts with email, contacts with phone, and contacts with LinkedIn profiles

**Company Detail Page:** Click any company to open a dedicated detail page with five tabs — Contacts, Overview, Discovery & Fit, Budget Signals, and Urgency Signals — providing full transparency into every piece of data and reasoning behind the qualification.

---

## 7. On-Demand Signal Rediscovery

You can now **re-trigger signal research for individual companies** directly from the Company Detail page, without re-running the entire pipeline.

**When to use it:**

- A company was found but signals are missing or incomplete
- You want to refresh stale data with the latest information
- You want to check if new budget or urgency signals have emerged since the last search

**How it works:**

1. Open any company's detail page
2. If signals are missing, you'll see a **"Discover Signals"** button with a dropdown to choose:
   - **Budget & Urgency** (both)
   - **Budget Only**
   - **Urgency Only**
3. Click to start — the system runs the same AI-powered signal research used in the full pipeline, but targeted at just this one company
4. **Real-time progress** streams to your screen: you can see which tools are being used, what the AI is finding, and when it completes
5. Scores update automatically when discovery finishes

**Re-discover existing signals:** If a company already has signals, the tab headers for Budget Signals and Urgency Signals show a **"Re-discover"** button to refresh the data with the latest available information.

**Contact rediscovery:** Similarly, the Contacts tab shows a **"Discover Contacts"** or **"Re-discover Contacts"** button to find new decision-makers or refresh existing contact data for that company.

**Progress survives navigation:** If you start a discovery and navigate away, it continues in the background. When you return to the company page, the progress picks up where you left off.

---

## 8. Tool Effectiveness Monitoring (Super Admin)

Super Admins now have a dedicated **Tools** page for monitoring how well each data source is performing and making informed decisions about tool configuration.

**Tab 1 — Tool Registry:**

An overview of all integrated data tools with real-time health and usage metrics:

- **Health status dashboard** — At-a-glance counts of Healthy, Unhealthy, No API Key, and Disabled tools
- **Category filters** — View tools by type: Pipeline (data sourcing), Research (enrichment), or Co-pilot DB (internal queries)
- **Per-tool metrics:**
  - Health status (healthy / unhealthy / no API key)
  - API key configuration status
  - Success rate (percentage of calls that returned results)
  - Total API calls made
  - Rate limit information
  - Last used timestamp
  - Last error message
  - Priority score (0–100, higher = more preferred)
  - Enabled/disabled toggle
- **Health check** — Run a health check on any individual tool or all tools at once to verify connectivity and API key validity

**Tab 2 — Tool Effectiveness:**

Deeper analytics on which tools are actually producing qualified leads:

- **Cross-run aggregate table** — For each tool, see: total companies sourced, companies that passed qualification, pass rate, average final score, effectiveness score, and number of runs used. Segmented by industry and country where applicable.
- **AI-generated insights panel** — Automatic recommendations:
  - High performers (70%+ pass rate) highlighted in green
  - Underperformers (<20% pass rate) flagged with a suggestion to consider disabling
  - Borderline tools (40–69% pass rate) marked for monitoring
- **Per-run breakdown** — Select any completed pipeline run to see:
  - Stacked bar chart showing each tool's contribution (High Fit / Medium Fit / Low Fit companies)
  - Detailed table: companies discovered, qualified, disqualified, fit distribution, efficiency rate, average score, and top 3 company examples
  - Enrichment tool metrics: total calls, successes, failures, and success rate

**Auto-disable:** Tools that consistently fall below their effectiveness threshold (default: 20% pass rate) are automatically flagged and deprioritized by the system. Super Admins can manually re-enable them via the toggle.

---

## 9. Improved Signal Recency in Search Logic

The search engine now **prioritizes recent signals over outdated ones**, ensuring that lead scores reflect the current state of a company rather than historical data.

**How recency scoring works:**

| Evidence Age | Weight |
|---|---|
| Less than 1 month | Full weight (1.0x) |
| 1–3 months | 0.85x |
| 3–6 months | 0.6x |
| More than 6 months | 0.3x |
| Unknown / no date | 0.5x (penalized) |

**What this means in practice:**

- A $20M funding round from last month scores significantly higher than a $200M round from 18 months ago
- Hiring sprees from the past few weeks are weighted heavily; job postings from a year ago are discounted
- The AI agent is explicitly instructed to include evidence dates with every signal it finds, and signals without dates are penalized

**Deal Hotness scoring:** Each company now receives a **Deal Hotness** tier based on the combination of budget signals, urgency signals, and evidence recency:

| Tier | Score | What It Means |
|---|---|---|
| Hot | 75–100 | Strong, recent signals across both budget and urgency — high-priority lead |
| Warm | 50–74 | Moderate signals with some recent evidence — worth pursuing |
| Cool | 25–49 | Weak or dated signals — may need more research |
| Cold | Below 25 | No meaningful recent signals — low priority |

A recency bonus of up to 10 points is added for companies with very fresh evidence (under 1 month old).

**Cross-run intelligence:** The system also learns from previous runs — tools and query patterns that produced high-scoring, qualified leads are prioritized in future searches for similar ICP profiles.

---

## 10. User Activity Monitoring (Admin & Super Admin)

Admins and Super Admins now see an **Administration** section on their Dashboard with visibility into team activity across the platform.

**Overview metrics:**
- Total Users
- Active Users (signed in within the last 7 days)
- Total ICPs created (across all users)
- Total Searches run (across all users)

**Three-tab activity view:**

**Users tab:**
- Table of all users with: name, email, profile picture, role (color-coded badge), ICP count, search count, and last activity (displayed as relative time — "2h ago", "3d ago", etc.)
- Search by name or email
- Filter by role (User / Admin / Super Admin)

**Searches tab:**
- Recent pipeline runs across all users
- Shows: search name (linked to results), user who ran it, status (completed/running/failed), companies found, contacts found, and date
- Filter by status

**ICPs tab:**
- Recently created ICP configurations across all users
- Shows: ICP name (linked to editor), user who created it, and creation date

**Audit Logs (Super Admin only):**
- Complete audit trail of all significant actions: ICP creation/updates/deletions, pipeline runs/cancellations, and user management changes
- Each entry records: who performed the action, what they did, which resource was affected, the IP address, and the timestamp
- Filterable by resource type and user

---

*For questions or feedback, reach out to the qlGen product team.*
