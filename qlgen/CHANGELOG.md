# qlGen Changelog

*Last updated: May 11, 2026*

---

## What's New in qlGen

### Signal Research & Company Tracking (May 2026 — in progress)

A new persistent monitoring layer that lets you track qualified companies over time and receive real-time buying signals without re-running full pipeline searches.

#### Tracking Lists

Organise your best prospects into named **Tracking Lists** — persistent watchlists that survive individual pipeline runs.

- **Create & manage lists** — Create any number of named lists with an optional description from the new `/tracking` page
- **Add companies from search results** — Select one or more companies on the Leads page or All Leads page and click **"Add to Tracking List"** to promote them directly from a pipeline run
- **Ingest companies externally** — Upload a CSV/Excel file or paste a list of company names/domains on the new **Ingest** page (`/ingest`); qlGen matches rows against the knowledge base, creates new entries where needed, and optionally auto-adds results to a target tracking list
- **Table & Kanban views** — Each tracking list detail page (`/tracking/:listId`) offers both a sortable table view and a Kanban board grouped by outreach status
- **Outreach status tracking** — Track each company through custom outreach stages (e.g. "To Reach", "In Conversation", "Closed"); update status, add notes, apply tags, and snooze companies directly from the list view
- **Contact enrichment** — Enrich decision-maker contacts for all companies in a list, or for a single company, directly from the tracking list detail page; enrichment status is shown per company

#### Signal Feed

A unified **Signal Feed** page (`/signals`) streams buying signals detected across all your tracking lists.

- **On-demand signal detection** — Trigger signal research for any individual company or for all companies in a tracking list simultaneously
- **Signal types** — Detects budget signals (funding rounds, revenue growth, budget announcements), urgency signals (hiring sprees, tech adoption, expansion), and custom signal types
- **Signal timeline** — Per-company signal history is displayed as a chronological timeline within the tracking list detail view
- **Signal hints** — Each tracking list can be configured with custom signal hints (specific budget keywords, urgency phrases, target roles) via a **Signal Hints Drawer**; hints are used to focus signal detection on what matters most for that list
- **Dismiss signals** — Mark irrelevant signals as dismissed; expired signals are automatically archived
- **Signal heat score** — Each tracked company receives a dynamically recomputed heat score based on the recency and strength of its detected signals; lists sort by heat score by default

#### Account Briefs

Generate a concise, AI-written **Account Brief** for any tracked company with a single click.

- Pulls together company overview, ICP fit summary, key signals, and contact information into a formatted markdown document
- Accessible from the tracking list detail page via the **"Brief"** button per company
- Brief can be copied to clipboard or printed directly from the modal

#### Notification Bell

A new **Notification Bell** icon in the navigation bar surfaces in-app alerts.

- Unread count badge updates every 30 seconds
- Notification types include: signal detected, monitoring complete, ingest complete, and outreach reminder
- Click any notification to navigate directly to the relevant tracking list or signal; mark individual notifications or all as read

#### Dashboard Tracking Stats

The Dashboard now shows three new metric tiles in a dedicated **Tracking** row:

- **Tracking Lists** — Total number of lists created; click to navigate to `/tracking`
- **Tracked Companies** — Total companies across all lists; click to navigate to `/tracking`
- **Active Signals** — Total signals in the signal feed; click to navigate to `/signals`

#### Database Migrations

- `l2m3n4o5p6q7` — Creates `tracking_lists`, `tracking_list_memberships`, `signal_events`, `notifications`, `tags`, and `ingest_batches` tables
- `m3n4o5p6q7r8` — Adds `signal_hints` JSONB column to `tracking_lists` and `enrichment_status` to `tracking_list_memberships`

---

### Evaboot Integration Enhancements (April 30, 2026)

Expanded Evaboot LinkedIn export support with richer company data, credit management, and database schema improvements.

- **New company fields** — LinkedIn Sales Navigator URL, LinkedIn company ID, LinkedIn profile URL, and employee count from LinkedIn now stored per company and exposed in exports and the Co-Pilot
- **Daily credit limits** — Per-user daily credit limit tracking for Evaboot exports; admins can set and update limits from the User Management page. Requests that exceed the limit are rejected with a clear error message
- **VARCHAR column widening** — Database columns previously capped at 100 characters have been widened to prevent truncation of long LinkedIn URLs, industry strings, and similar fields
- **Pipeline & export updates** — Pipeline service, export service, and Co-Pilot DB tools updated to surface the new fields in results and XLSX/CSV exports
- **Frontend updates** — ICP Config, Pipeline, Company Detail, and User Management pages reflect the new fields and credit limit controls

---

### Evaboot Integration (April 6, 2026)

qlGen can now import leads directly from LinkedIn Sales Navigator via Evaboot CSV exports.

- **Evaboot discovery mode** — Upload a CSV exported from Evaboot (LinkedIn Sales Navigator) on the ICP Config page; qlGen ingests the companies, enriches them through the standard pipeline, and scores them against your ICP criteria
- **Sales Navigator URL parser** — Frontend utility parses Evaboot CSV format and maps columns to qlGen's internal schema
- **Admin API** — New admin endpoints for managing Evaboot configuration and credit usage
- **Tool registry updates** — Evaboot tool registered and tracked alongside other data sources; tool effectiveness metrics include Evaboot-sourced companies
- **Dashboard enhancements** — Dashboard page updated to display Evaboot run status and discovery metrics

---

### Outreach Email & Evidence Display (March 25, 2026)

- **Outreach email generation** — Pipeline page now supports generating a personalised outreach email for any qualified company directly from the leads view
- **Evidence Display component** — A new shared `EvidenceDisplay` component renders structured signal evidence (source, date, quote) consistently across Company Detail and Leads pages
- **Pipeline page improvements** — Outreach email modal integrated into the pipeline results UI; evidence sections in Budget Signals and Urgency Signals tabs refactored to use the new component

---

### Help & Feedback System (March 25, 2026)

- **Help menu** — A new **Help** popover in the navigation bar replaces the static user guide icon, offering quick access to the User Guide, Submit Feedback, and My Submissions
- **Feedback submission** — Users can submit feedback, bug reports, complaints, and feature requests with a priority level directly from the app
- **My Submissions** — Users can track the status of their own submissions and read admin replies inline
- **Admin Feedback page** — Super Admins have a dedicated `/admin/feedback` page to view all submissions, update statuses, and reply to individual entries
- **Backend** — `Feedback` and `FeedbackReply` models, Pydantic schemas, 5 API endpoints with auth and audit logging, and an Alembic migration

---

### Infrastructure Scaling & Reliability (March 25, 2026)

Major infrastructure and backend reliability improvements to support concurrent pipelines at scale.

- **10 concurrent pipelines** — A semaphore-based concurrency gate limits simultaneous pipeline runs to 10; requests beyond capacity receive an HTTP 429 with a friendly message
- **Bedrock upgrade** — AI model upgraded to Claude Sonnet 4.5 (10K RPM quota) for higher throughput
- **Redis ElastiCache** — Cross-task SSE event broadcasting now uses Redis, enabling real-time pipeline progress streaming across multiple ECS tasks
- **ECS scaling** — Task size increased to 4 vCPU / 8 GB RAM; autoscaling configured up to 8 tasks; uvicorn workers increased to 4
- **Bedrock throttle retry** — All agent calls include exponential backoff retry on throttling errors to reduce failed runs during peak load
- **Database pool tuning** — SQLAlchemy connection pool configured with `pool_size=5`, `max_overflow=10`, `pool_recycle`, and `pool_pre_ping` for long-lived ECS tasks
- **Apollo tool enhancements** — Expanded search strategies, improved deduplication, and additional pagination handling
- **Exa tool refactor** — Cleaner query construction and better error handling for web research calls
- **Clay tool removal** — `clay_tool.py` removed after the Clay API was deprecated; searches now rely on the remaining active tool set

---

### Home Page & All Leads Improvements (March 24, 2026)

- **Home page** — New `/home` route with a hero landing view; post-login redirects land on Home; Dashboard remains accessible via the sidebar
- **All Leads metrics** — Two new metric tiles on the All Leads tab: **Total Companies** and **Total Contacts** across all pipeline runs; click a tile to open a detail modal
- **Industry / Country filters** — Moved into the card header alongside the sort dropdown for a cleaner layout
- **Company Detail UX** — Back-navigation returns to the correct tab (All Leads vs. Dashboard); active sidebar nav item syncs to the originating tab; hotness property shown in Overview tab; action buttons repositioned to the top with the page heading on the left
- **Heading renames** — "Contacts" tab heading renamed to "Contacts List"; "Budget Signals" and "Urgency Signals" section headings updated for consistency

---

### AI Co-Pilot (NEW)

A conversational AI assistant is now available across all pages. Click the floating chat button to open the Co-Pilot panel.

- **Context-aware help** — The Co-Pilot knows which page you're on and tailors its suggestions accordingly (e.g., lead analysis on the Leads page, ICP refinement tips on the ICP Config page).
- **Deep data exploration** — Ask natural language questions about your leads, companies, contacts, and pipeline results. The Co-Pilot can search your data semantically (by meaning) or with structured filters.
- **Research tools** — The Co-Pilot can pull live data from LinkedIn, SEC filings, Google Places, news sources, financial databases, and more to enrich your understanding of a prospect.
- **Persistent sessions** — Chat history is saved so you can pick up where you left off.

---

### Company Detail Page (NEW)

Click any company in your search results to open a dedicated detail view with five tabs:

- **Contacts** — All discovered contacts with confidence scores
- **Overview** — Company profile, qualification status, and key metrics
- **Discovery & Fit** — How the company was found and how it matches your ICP criteria
- **Budget Signals** — Financial indicators and funding information
- **Urgency Signals** — Hiring activity, technology adoption, and timing indicators

---

### Unified All Leads Page (NEW)

Browse companies across all your pipeline runs in one place.

- View and filter leads from every search you've run, not just one at a time
- Server-side pagination, sorting, and filtering for fast performance
- Accessible from the dashboard stats panel

---

### Tools Management Page (NEW — Admin Only)

A new admin-only page for monitoring and managing the tool ecosystem:

- **Tool Registry** — See all available data tools, their status, and configuration
- **Tool Effectiveness** — Analyze which tools are performing well per run or across all runs, with quality metrics and insights
- **Auto-disable** — Tools that consistently underperform are automatically deprioritized based on effectiveness scoring

---

### Search Quality Improvements

Major improvements to how qlGen discovers companies:

- **Cross-run learning** — The system remembers what worked in previous runs and applies that intelligence to new searches
- **Better coverage** — Expanded industry synonyms (15 industries), geographic hub mapping (16 countries), and structured recall tiers ensure broader discovery
- **Apollo auto-pagination** — Apollo searches now automatically page through results instead of stopping at the first page, dramatically increasing the number of companies found
- **Smart batching** — Companies are prioritized by data quality for enrichment, so the best leads get processed first
- **New data sources** — Added French company registry (12M+ entities) and Nordic company registry (Denmark, Norway, Sweden)
- **Broken tool cleanup** — Removed tools that were returning errors (deprecated APIs, rate-limited endpoints) so searches run cleaner and faster

---

### Authentication & Authorization

- **Google OAuth sign-in** — Users now sign in with their Google account
- **Role-based access control (RBAC)** — Admin and standard user roles with appropriate access restrictions
- **Data isolation** — Users only see their own ICPs and pipeline results
- **Audit logging** — Administrative actions are tracked for compliance

---

### ICP Configuration Improvements

- **Clone an ICP** — Duplicate an existing ICP profile to create a variation without starting from scratch. Available from the ICP list page.
- **AI-assisted ICP creation** — The import section has been streamlined with a unified "Create with AI / Upload" button for faster setup
- **Simplified criteria** — Priority areas field removed to reduce complexity
- **Improved fit labels** — Firmographic fit status now shows "High Fit" / "Low Fit" instead of "Pass" / "Fail" for clearer communication

---

### Pipeline & Scoring Enhancements

- **Dynamic BANT scoring** — BANT (Budget, Authority, Need, Timeline) scoring adapts based on available data signals rather than rigid rules
- **Pipeline transparency** — Real-time visibility into what the AI agent is doing at each stage, including tool usage and reasoning
- **Tool registry** — Backend tracks which tools are used, their success rates, and response times
- **Strict mode** — Tighter qualification thresholds available for higher-quality lead output

---

### Dashboard & Reporting

- **Enhanced dashboard** — Updated stats and visualizations for pipeline results
- **Improved exports** — Styled XLSX and CSV exports for sharing lead data externally
- **Pipeline log replay** — SSE events are persisted, allowing you to review past pipeline runs without re-running them

---

### UI & Experience

- **New welcome page** — Redesigned landing page with animated onboarding flow
- **Refreshed navigation** — Updated sidebar layout with clearer organization
- **Co-Pilot button behavior** — The floating chat button hides when the panel is open to prevent overlap
- **Responsive polish** — Various layout and styling improvements across all pages

---

### Infrastructure

- **AWS hosting** — Application deployed on AWS (ECS Fargate + CloudFront + RDS PostgreSQL)
- **Semantic search** — Company data is embedded using AWS Bedrock Titan for vector similarity search (pgvector)
- **Auto-pagination** — API endpoints support server-side pagination for large datasets

---

*For questions or feedback, reach out to the qlGen product team.*
