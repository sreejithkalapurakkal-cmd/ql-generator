# qlGen Changelog

*Last updated: March 23, 2026*

---

## What's New in qlGen

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
