# qlGen Signal Intelligence Platform — Architecture Revamp

## Executive Vision

Transform qlGen from an ICP-based lead generation tool into a **world-class AI-native sales intelligence platform** that combines deep company research, buying signal detection, prospect enrichment, and outreach preparation into a single, premium workflow.

The system should feel like having an elite AI sales research analyst working 24/7 — one that reasons deeply, correlates weak signals across multiple sources, synthesizes intelligence, and generates actionable outreach context that enterprise sales teams can trust.

**Design North Star:** Quantiv-grade UX quality meets qlGen's existing 45+ tool research depth.

---

## Table of Contents

1. [Product Vision & User Workflows](#1-product-vision--user-workflows)
2. [UX Architecture](#2-ux-architecture)
3. [Backend Architecture](#3-backend-architecture)
4. [Agent Architecture](#4-agent-architecture)
5. [Tool Architecture](#5-tool-architecture)
6. [Data Models](#6-data-models)
7. [Event & Activity Feed Architecture](#7-event--activity-feed-architecture)
8. [Research Brief Architecture](#8-research-brief-architecture)
9. [Signal Intelligence Architecture](#9-signal-intelligence-architecture)
10. [Contact Enrichment Architecture](#10-contact-enrichment-architecture)
11. [Outreach Generation Architecture](#11-outreach-generation-architecture)
12. [Custom Signal Sources Architecture](#12-custom-signal-sources-architecture)
13. [AI Orchestration Strategy](#13-ai-orchestration-strategy)
14. [Caching Strategy](#14-caching-strategy)
15. [Memory Strategy](#15-memory-strategy)
16. [Observability Strategy](#16-observability-strategy)
17. [Scalability Strategy](#17-scalability-strategy)
18. [Cost Optimization Strategy](#18-cost-optimization-strategy)
19. [Security Considerations](#19-security-considerations)
20. [Phased Implementation Roadmap](#20-phased-implementation-roadmap)
21. [Tech Stack & APIs](#21-tech-stack--apis)
22. [Example Workflows](#22-example-workflows)
23. [Risks & Mitigation](#23-risks--mitigation)
24. [Metrics & KPIs](#24-metrics--kpis)
25. [Future Extensibility](#25-future-extensibility)

---

## 1. Product Vision & User Workflows

### Core Value Proposition

qlGen becomes the first platform that combines:
- **Signal Detection** (UserGems/Bombora-class) with
- **Deep Research** (45+ tools, AI synthesis) with
- **Outreach Generation** (signal-anchored, evidence-backed) with
- **Transparent AI** (full explainability, confidence scoring, citation chains)

### Primary User Workflows

#### Workflow 1: Conference List → Tracked Intelligence → Outreach
```
Upload CSV (500 companies)
  → Configure signal hypotheses (budget, urgency, custom signals)
  → Firmographic filtering (reduce to 80 high-fit companies)
  → Promote survivors to Tracking List
  → AI runs deep research on each company
  → Signals detected and ranked by composite heat
  → Research briefs auto-generated for top accounts
  → Contacts enriched asynchronously
  → Outreach drafts generated anchored to detected signals
  → Sales rep reviews, edits, sends
  → Outcomes tracked, signal weights adjusted
```

#### Workflow 2: Continuous Monitoring → Proactive Intelligence
```
Tracking lists monitored on schedule (daily/weekly)
  → New signals detected across all tracked companies
  → Signal heat scores updated with decay
  → High-priority signals trigger auto-brief regeneration
  → Notifications pushed to user
  → Signal feed surfaces ranked, actionable items
  → Quick actions: Draft outreach, snooze, dismiss, add to list
  → Activity feed narrates research in human-friendly language
```

#### Workflow 3: Deep Account Research → Sales Preparation
```
User opens company detail page
  → Executive summary with AI-generated overview
  → Research brief: 8 sections with citations and confidence
  → Signal timeline: chronological company developments
  → Contact intelligence: stakeholders, decision makers, influence
  → Outreach workspace: AI-drafted emails, talk tracks, discovery questions
  → All evidence is cited, expandable, and confidence-scored
```

#### Workflow 4: Custom Signal Monitoring
```
User defines custom signal rules
  → Keyword triggers (e.g., "cloud migration", "data platform")
  → Hiring pattern triggers (e.g., "VP+ in Data")
  → Tech stack change triggers (e.g., "added Snowflake")
  → Company event triggers (e.g., acquisition, IPO)
  → Signals from custom sources (careers pages, blogs, GitHub)
  → Cross-source correlation amplifies confidence
  → Custom signals appear in same feed with standard signals
```

---

## 2. UX Architecture

### Design System (Quantiv-Inspired)

**Color Palette:**
- Primary Accent: Indigo/Iris family (`#444ce7` primary, scale from 50-900)
- Neutrals: Comprehensive gray scale (`#f9fafb` → `#111827`)
- Semantic: Emerald (high confidence), Amber (medium), Gray (low)
- Signal Types: Purple (leadership), Blue (earnings), Sky (hiring), Green (funding), Orange (product launch)

**Typography:**
- UI Font: Inter (sans-serif)
- Monospace: JetBrains Mono (for source citations, version numbers, technical data)
- Scale: xs (10px), sm (14px), base (16px), lg (18px), xl (20px)

**Spacing:** 4px base unit, consistent use of gap-3/4/6 between sections

**Components:**
- Cards: White background, `border-gray-200`, `rounded-lg`, subtle shadow
- Badges: Color-coded by semantic meaning (confidence, signal type, status)
- Buttons: Primary (solid accent), Secondary (white + border), Ghost (transparent)
- Banners: Info (blue), Warning (amber), Error (red) — dismissible
- Tables: Clean header with uppercase labels, hover rows, inline actions

### Navigation Architecture

```
Sidebar (fixed, 240px)
├── Main
│   ├── Home (Dashboard)           → /
│   ├── Signal Feed                → /signals
│   └── Accounts                   → /accounts
├── Research
│   ├── ICPs                       → /icps
│   ├── Pipeline                   → /pipeline
│   └── All Leads                  → /leads
├── Workspace
│   ├── Custom Signals             → /custom-signals
│   ├── Ingest                     → /ingest
│   └── Settings                   → /settings
└── Admin
    ├── Tools                      → /admin/tools
    └── Users                      → /admin/users

Top Bar (fixed)
├── Page Title (context-aware)
├── Global Search
├── Notification Bell (unread count badge)
└── User Avatar + Dropdown
```

### Page Architecture

#### 2.1 Home / Dashboard (`/`)

**Layout:** Stats strip + two-column grid (2:1 ratio)

**Components:**
```
┌─────────────────────────────────────────────────────────────┐
│  Good morning, {name} · {date} · Here's what moved today   │
├─────────────────────────────────────────────────────────────┤
│  [Accounts]  [Signals Today]  [Open Drafts]  [Briefs]      │  ← Stats strip (4 KPIs)
├──────────────────────────────────┬──────────────────────────┤
│  Top Signals Today               │  Saved Signals           │
│  ┌──────────────────────────┐   │  ┌──────────────────┐    │
│  │ [confidence] [type]      │   │  │ • Meridian Health │    │
│  │ Account · Region         │   │  │   CDO appointment │    │
│  │ Headline (bold)          │   │  └──────────────────┘    │
│  │ AI one-liner (gray)      │   │                          │
│  │ Source · Date             │   │  Drafts in Progress      │
│  └──────────────────────────┘   │  ┌──────────────────┐    │
│  (up to 4 signal cards)         │  │ Email to J.Smith  │    │
│                                  │  │ Hook: CDO signal  │    │
│                                  │  └──────────────────┘    │
└──────────────────────────────────┴──────────────────────────┘
```

**Cold Start State:** Signal Agent initialization banner with progress bar and estimated time.

#### 2.2 Signal Feed (`/signals`)

**Layout:** Master-detail with sliding detail pane

**Components:**
```
┌────────────────────────────────────┬──────────────────────────┐
│  ● Live · refreshed 3s ago    [↻] │                          │
│                                    │  Signal Detail Pane      │
│  ┌────────────────────────────┐   │  (420px, sticky)         │
│  │ [All] [Today] [Week] [Saved]│   │                          │
│  │ Show low confidence [toggle]│   │  Account header          │
│  │ [Type ▾] [Conf ▾] [Region ▾]│  │  Breadcrumb              │
│  └────────────────────────────┘   │  Agent attribution        │
│                                    │                          │
│  ┌────────────────────────────┐   │  Confidence + Type       │
│  │ Signal Row (clickable)      │   │  Source headline          │
│  │ [●] [High] [Funding]       │   │  Source citation card     │
│  │ Arcturus Capital · NA       │   │  "Why this matters" (AI) │
│  │ Closes $120M Series C       │   │  Research brief link      │
│  │ Post-close headcount...     │   │  Actions (Save/Dismiss)  │
│  │ Press release · Apr 27      │   │                          │
│  └────────────────────────────┘   │  ┌────────────────────┐  │
│  (scrollable feed, sorted by      │  │ Draft email outreach│  │
│   confidence → recency)           │  │ Draft LinkedIn msg  │  │
│                                    │  └────────────────────┘  │
└────────────────────────────────────┴──────────────────────────┘
```

**Key UX Decisions:**
- Live refresh indicator with green pulse dot
- Snooze return notice (amber banner with count)
- EU coverage notice (info banner, dismissible)
- Confidence explainer on click ("What does this mean?")
- Stale signal warning (>30 days old)
- Auto-generated brief notice when signal triggers brief creation

#### 2.3 Accounts Listing (`/accounts`)

**Layout:** Filter bar + sortable table

**Columns:** Account (initials + name + domain), Industry, Region, ICP Fit (badge with score), Signals (count), Brief (Ready/None), Drafts (count), Tags

**Filters:** Search, ICP Fit, Region, Status (monitored/paused/archived), Tag

**Actions:** Import CSV, Discover Lookalikes (AI-powered)

**Row Click:** Navigate to Account Profile

**Premium Touches:**
- ICP Fit badge with color coding (strong=emerald, moderate=amber, weak=gray)
- Signal count as active indicator
- Brief status shows "Ready" or "None" with appropriate styling
- Tags as pill badges
- Hover row highlight with transition

#### 2.4 Account Profile (`/accounts/:id`) — THE KEY PAGE

**Layout:** Header card + tabbed content (5 tabs)

```
┌─────────────────────────────────────────────────────────────┐
│  ← Accounts                                                  │
│                                                              │
│  [Unassigned owner banner / Paused banner / Archived banner] │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  [MH]  Meridian Health Systems  [Strong Fit 92]      │   │
│  │        Healthcare · 5000-10000 · North America       │   │
│  │        meridianhealth.com ↗                          │   │
│  │        [Enterprise] [Healthcare] [Conference Q2]     │   │
│  │                                    [Draft email] [Brief] │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  [Overview] [Signals (5)] [Research brief] [Drafts (2)] [Contacts (4)] │
│  ─────────────────────────────────────────────────────────── │
│                                                              │
│  Tab Content (see below)                                     │
└─────────────────────────────────────────────────────────────┘
```

**Overview Tab:**
- 4-column KPI strip: Signals detected, Open drafts, Research brief (Ready/None), ICP Score
- Latest signals preview (3 most recent)
- Open drafts section

**Signals Tab:**
- Vertical timeline with confidence-colored dots
- Connected by vertical gray line
- Each entry: Type badge + Confidence badge + Date + Headline + AI summary + Source

**Research Brief Tab:**
- Current brief card with accent border
- 5+ structured sections with expandable content
- Revision history with version tags
- "Generate brief" CTA if none exists
- "Regenerate" button to refresh with latest signals

**Drafts Tab:**
- Draft cards with format icon (Email/LinkedIn)
- Status badge (In progress/Sent/Discarded)
- Recipient, subject, hook signal summary

**Contacts Tab:**
- Table: Name (avatar + primary badge), Title, Email, LinkedIn, Draft button
- EU resident warnings with GDPR context
- Enrichment progress indicator for in-progress enrichments

#### 2.5 Research Brief (`/accounts/:id/brief`) — DEEP INTELLIGENCE WORKSPACE

**Layout:** Sticky TOC sidebar (208px) + main content area

```
┌───────────┬──────────────────────────────────────────────────┐
│  Contents │  Meridian Health Systems — Research Brief         │
│           │  [v3] 920 words · 8 sections · AI generated      │
│  🏢 Company│  Research Agent · Auto-generated when             │
│  👥 Org    │  ⚡ New CDO appointed fired · Apr 28, 2026        │
│  ⚡ Signals│  [v3 ▾] [Regenerate] [Export PDF]                │
│  🎯 Competitive│                                              │
│  ⚙️ Tech  │  ┌──────────────────────────────────────────┐    │
│  💰 Budget│  │  🏢 Company Overview                01/08 │    │
│  ⏱️ Why Now│  │                                          │    │
│  💬 Angle │  │  Meridian Health Systems is a large       │    │
│           │  │  integrated healthcare network [1]...     │    │
│  Revisions│  │                                          │    │
│  v3 Apr28 │  │  • 14-state hospital network + 60 clinics│    │
│  v2 Apr14 │  │  • Recently completed Epic EHR rollout    │    │
│  v1 Mar30 │  │  • New CDO appointed April 2026           │    │
│           │  │                                          │    │
│           │  │  Sources: [SEC filing ↗] [Web change ↗]   │    │
│           │  └──────────────────────────────────────────┘    │
│           │                                                  │
│           │  (8 sections, progressively revealed during gen) │
└───────────┴──────────────────────────────────────────────────┘
```

**Brief Sections:**
1. **Company Overview** — Size, industry, key facts, public/private status
2. **Org Structure & Key Contacts** — Decision makers, reporting lines, procurement authority
3. **Recent Signals (Last 30 Days)** — Detected signals with confidence and evidence
4. **Competitive Landscape** — Current vendor stack, known evaluations, displacement opportunities
5. **Tech Stack & Infrastructure Signals** — Technical environment, migration patterns
6. **Budget & Spend Indicators** — Disclosed budgets, estimated spend capacity, procurement cycles
7. **Why Now** — Timing analysis, urgency windows, optimal outreach period
8. **Recommended Angle & Talk Tracks** — Opening hooks, key messages, proof points, channels

**Premium Features:**
- **Inline citations** — `[1]` badges that highlight corresponding source chips on click
- **Source chips** — Clickable, with source class (SEC filing, Press release, Hiring signal)
- **Progressive streaming** — Sections appear one by one with skeleton placeholders
- **Revision dropdown** — Navigate between brief versions with trigger signal attribution
- **Insufficient data state** — Sections without enough data show dashed placeholder
- **Scanning animation** — Spinner during initial signal analysis phase
- **Streaming cursor** — Blinking accent cursor on section being generated
- **Intersection observer** — TOC highlights active section on scroll

#### 2.6 Custom Signals (`/custom-signals`)

**Layout:** Rule list table + sliding rule editor panel

**Rule Types:**
- Keyword Match — fires when monitored sources mention specific keywords
- Hiring Pattern — fires when companies post matching job titles
- Tech Stack Change — fires on tracked technology additions/removals
- Company Event — fires on specific event types (acquisition, merger, IPO, etc.)

**Rule Configuration:**
- Name, Trigger Type (2x2 grid of selectable cards)
- Conditions (tag input for keywords/titles, checkboxes for events)
- Scope (all accounts, monitored only, tagged accounts)
- Action (create signal, signal + brief, notify only)
- Confidence override (high/medium/low toggle)

#### 2.7 Draft Drawer (Global Overlay)

**Layout:** 580px sliding panel from right, overlay with backdrop

**Components:**
- Outreach Agent attribution badge
- Hook signal pill (linked to triggering signal)
- Contact picker dropdown
- Format toggle (Email / LinkedIn)
- Voice profile selector (Concise / Consultative / Formal)
- Tone override pills (Direct / Consultative / Formal / Casual)
- Subject input (email only)
- Message textarea with character counter
- Inline warnings: Edited draft notice, banned phrase detection, stale hook signal
- Footer: Regenerate, Discard, Copy, Mark as Sent (with confirmation flow)

#### 2.8 Activity Feed (Research Narrative)

**Current Problem:** Raw agent logs like "Executing search agent" and "LLM tool invocation completed"

**New Design:** Human-friendly research narration that feels like an analyst working

**Activity Categories:**
```
🔍 Research Activities
   "Analyzing recent hiring trends in cybersecurity roles at Meridian Health"
   "Scanning SEC filings for budget disclosures (FY2026 10-K)"
   
⚡ Signal Detection
   "Detected rapid expansion in AI infrastructure hiring (+23 roles)"
   "Identified CDO appointment — Dr. Priya Nair, ex-Kaiser Permanente"
   
🔗 Correlation Events
   "Correlating CDO appointment with $40M digital health initiative"
   "Cross-referencing hiring surge with Tableau renewal timeline"
   
📊 Synthesis Events
   "Generating research brief section: Why Now"
   "Updating signal heat score: 72 → 89 (+17)"
   
✅ Completion Events
   "Research brief v3 ready — 920 words, 8 sections"
   "Contact enrichment complete — 4 decision makers identified"
```

**Multi-level Verbosity:**
- **Summary** (default): One-line human narrations, grouped by milestone
- **Detailed**: Expandable cards with reasoning, evidence, confidence
- **Technical**: Full tool call traces, timing, token counts (for debugging)

### Component Architecture

```
src/
├── components/
│   ├── accounts/
│   │   ├── AccountRow.tsx              # Table row with badges
│   │   ├── AccountFilters.tsx          # Filter bar with dropdowns
│   │   └── IcpFitBadge.tsx             # Color-coded ICP fit indicator
│   ├── signals/
│   │   ├── SignalRow.tsx               # Feed row (compact)
│   │   ├── SignalDetailPane.tsx        # Sliding detail panel
│   │   ├── SignalTimeline.tsx          # Vertical timeline with dots
│   │   ├── SignalCard.tsx              # Card variant (for dashboard)
│   │   └── FilterBar.tsx              # Tab + filter controls
│   ├── briefs/
│   │   ├── BriefViewer.tsx            # Full brief with TOC + citations
│   │   ├── BriefSection.tsx           # Individual section renderer
│   │   ├── CitedBody.tsx              # Text with inline citation badges
│   │   ├── RevisionDropdown.tsx       # Version switcher
│   │   └── SectionSkeleton.tsx        # Loading placeholder
│   ├── drafts/
│   │   ├── DraftDrawer.tsx            # Global overlay drawer
│   │   ├── ContactPicker.tsx          # Contact selection dropdown
│   │   └── VoiceProfileSelector.tsx   # Voice/tone controls
│   ├── contacts/
│   │   ├── ContactTable.tsx           # Contact list with actions
│   │   └── StakeholderMap.tsx         # Visual influence mapping (Phase 2)
│   ├── activity/
│   │   ├── ActivityFeed.tsx           # Research narrative feed
│   │   ├── ActivityItem.tsx           # Individual narration entry
│   │   └── VerbosityToggle.tsx        # Summary/Detailed/Technical
│   ├── home/
│   │   ├── StatsStrip.tsx             # KPI bar
│   │   ├── SignalCard.tsx             # Dashboard signal card
│   │   └── DraftCard.tsx              # Dashboard draft card
│   ├── custom-signals/
│   │   ├── RuleList.tsx               # Rules table
│   │   └── RulePanel.tsx              # Rule editor drawer
│   ├── layout/
│   │   ├── AppShell.tsx               # Shell with sidebar + topbar
│   │   ├── Sidebar.tsx                # Fixed sidebar nav
│   │   └── TopBar.tsx                 # Search + notifications
│   └── ui/
│       ├── Badge.tsx                  # Confidence, SignalType, Status badges
│       ├── Banner.tsx                 # Alert banners (info/warning/error)
│       ├── Button.tsx                 # Primary/Secondary/Ghost buttons
│       ├── Card.tsx                   # Card container
│       ├── EmptyState.tsx             # No-data placeholder
│       ├── Skeleton.tsx               # Loading skeletons
│       ├── SourceCitation.tsx         # Source chip component
│       └── Toggle.tsx                 # Switch toggle
├── context/
│   ├── SignalStateContext.tsx          # Signal lifecycle management
│   ├── DraftDrawerContext.tsx          # Global drawer state
│   └── PageContextProvider.tsx        # Page type for co-pilot
├── pages/
│   ├── Home.tsx                       # Dashboard
│   ├── SignalFeed.tsx                 # Signal feed with detail pane
│   ├── Accounts.tsx                   # Account listing
│   ├── AccountProfile.tsx             # Account detail (5 tabs)
│   ├── ResearchBrief.tsx              # Full brief viewer
│   ├── CustomSignals.tsx              # Custom signal rules
│   ├── IngestPage.tsx                 # Upload wizard
│   ├── ICPListPage.tsx                # (existing)
│   ├── ICPConfigPage.tsx              # (existing)
│   ├── PipelinePage.tsx               # (existing)
│   └── AllLeadsPage.tsx               # (existing)
├── api/
│   ├── client.ts                      # Axios instance
│   ├── signalApi.ts                   # Signal CRUD + feed
│   ├── accountApi.ts                  # Account + brief APIs
│   ├── draftApi.ts                    # Draft generation + lifecycle
│   ├── ingestApi.ts                   # Upload + mapping
│   ├── customSignalApi.ts             # Rule CRUD
│   ├── notificationApi.ts             # Notification fetch + mark read
│   └── ... (existing APIs)
└── types/
    └── index.ts                       # All TypeScript interfaces
```

### Frontend State Model

**Context Providers:**
- `SignalStateProvider` — Signal lifecycle (new/saved/acted_on/dismissed/snoozed), mute rules
- `DraftDrawerProvider` — Global drawer open/close with pre-populated options
- `NotificationProvider` — Unread count, notification list, mark-read
- `PageContextProvider` — Current page type for co-pilot recommendations

**Data Fetching:**
- React Query (TanStack Query) for server state management
- Optimistic updates for signal lifecycle changes (save/dismiss/snooze)
- SSE streams for: research progress, brief generation, contact enrichment
- Polling for: notification count (30s interval), signal feed refresh

**Streaming Enrichment Updates:**
- SSE endpoint per research job: `/api/v1/research/{job_id}/stream`
- Events: `section_started`, `section_complete`, `brief_ready`, `signal_detected`, `contact_found`
- Frontend updates sections progressively as they stream in

---

## 3. Backend Architecture

### Service Layer Architecture

```
backend/app/
├── api/                              # FastAPI route handlers
│   ├── router.py                     # Aggregates all sub-routers
│   ├── accounts.py                   # NEW: Account CRUD + listing + filters
│   ├── signals.py                    # Signal feed, detection, lifecycle
│   ├── briefs.py                     # Brief generation (SSE), retrieval, versions
│   ├── drafts.py                     # NEW: Draft generation, lifecycle, templates
│   ├── ingest.py                     # Upload, column mapping, enrichment
│   ├── tracking.py                   # Tracking list CRUD, members, outreach status
│   ├── custom_signals.py             # NEW: Custom signal rule CRUD
│   ├── notifications.py              # Notification list, mark read, unread count
│   ├── research.py                   # NEW: Research job management + SSE stream
│   ├── contacts.py                   # NEW: Contact enrichment + retrieval
│   ├── sources.py                    # NEW: Custom source management
│   ├── activity.py                   # NEW: Activity feed with narrative
│   ├── icp.py                        # (existing) ICP CRUD
│   ├── pipeline.py                   # (existing) Pipeline run + SSE
│   ├── leads.py                      # (existing) Results + export
│   ├── chat.py                       # (existing) Co-pilot
│   └── health.py                     # (existing) Health check
├── services/                          # Business logic
│   ├── signal_service.py             # Signal detection, scoring, decay
│   ├── signal_detection_service.py   # Tool-based signal detection
│   ├── brief_service.py              # Brief generation via Claude
│   ├── draft_service.py              # NEW: Outreach draft generation
│   ├── research_orchestrator.py      # NEW: Multi-agent research coordinator
│   ├── activity_narrator.py          # NEW: Event → human narration
│   ├── source_crawler.py             # NEW: Custom source crawling + change detection
│   ├── confidence_scorer.py          # NEW: Multi-factor confidence scoring
│   ├── signal_correlator.py          # NEW: Cross-signal correlation engine
│   ├── contact_enrichment_service.py # NEW: Async contact discovery
│   ├── custom_signal_evaluator.py    # NEW: Evaluate custom rules against signals
│   ├── tracking_list_service.py      # Tracking list management
│   ├── ingest_service.py             # Upload parsing + enrichment
│   ├── enrichment_service.py         # (existing) KB enrichment
│   ├── notification_service.py       # Notification management
│   ├── monitoring_service.py         # Scheduled signal monitoring
│   ├── export_service.py             # (existing) XLSX/CSV export
│   ├── embedding_service.py          # (existing) pgvector embeddings
│   └── pipeline_service.py           # (existing) Pipeline orchestration
├── agent/                             # AI agents
│   ├── research_planner_agent.py     # NEW: Plans research strategy per company
│   ├── signal_discovery_agent.py     # NEW: Discovers signals from sources
│   ├── research_synthesis_agent.py   # NEW: Synthesizes findings into briefs
│   ├── outreach_strategy_agent.py    # NEW: Generates signal-anchored outreach
│   ├── confidence_verification_agent.py # NEW: Verifies signal confidence
│   ├── signal_research_agent.py      # (existing) Signal research
│   ├── lead_gen_agent.py             # (existing) Pipeline agent
│   └── copilot_agent.py              # (existing) Co-pilot
├── tools/                             # External API integrations
│   ├── web_intelligence_tool.py      # NEW: Intelligent web crawling + summarization
│   ├── change_detection_tool.py      # NEW: Website change detection + diffing
│   ├── intent_signal_extractor.py    # NEW: Extract buying intent from text
│   ├── hiring_signal_detector.py     # NEW: Job posting analysis
│   ├── tech_stack_detector.py        # NEW: Technology detection from web/job posts
│   ├── executive_tracker.py          # NEW: Executive movement monitoring
│   ├── procurement_intel_tool.py     # NEW: Procurement portal scanning
│   ├── product_launch_detector.py    # NEW: Product/feature announcement detection
│   ├── ... (existing 20+ tools)
│   └── ddg_rate_limiter.py           # (existing) Rate limiting
├── models/                            # SQLAlchemy models
│   ├── ... (see Data Models section)
├── db/
│   └── session.py                     # Async engine + session factory
└── config.py                          # Pydantic Settings
```

### Event Bus Architecture

For real-time communication between services:

```python
# backend/app/events/event_bus.py

class EventBus:
    """In-process async event bus for service decoupling."""
    
    async def emit(self, event_type: str, payload: dict):
        """Emit event to all registered handlers."""
        
    def on(self, event_type: str, handler: Callable):
        """Register handler for event type."""

# Event Types:
# research.started        → Activity feed, UI progress
# research.section_done   → Brief progressive update
# research.completed      → Notification, signal heat recalc
# signal.detected         → Notification, heat update, custom rule eval
# signal.dismissed        → Heat recalc, feedback loop
# contact.enriched        → UI update, notification
# brief.generated         → Notification, account update
# draft.created           → Draft count update
# source.crawled          → Change detection, signal extraction
# monitoring.completed    → Batch notification
```

### Queue Architecture

For async processing (reusing existing thread pool pattern):

```python
# backend/app/workers/research_worker.py

class ResearchWorker:
    """Processes research jobs asynchronously."""
    
    async def execute_research(self, job_id: UUID, company_kb_id: UUID, config: ResearchConfig):
        """Run multi-stage research pipeline."""
        # Stage 1: Plan research strategy
        # Stage 2: Execute specialist agents in parallel
        # Stage 3: Synthesize findings
        # Stage 4: Generate brief
        # Stage 5: Detect signals
        # Stage 6: Enrich contacts
        # Each stage emits SSE events for real-time progress
```

**Execution Strategy:** 
- Phase 1: `asyncio.to_thread` + `ThreadPoolExecutor` (existing pattern)
- Phase 2: Migrate to `arq` (Redis-backed) when scale demands it
- Phase 3: AWS SQS + Lambda for serverless scaling

### Storage Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    PostgreSQL 16                         │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Core Tables  │  │ Signal Tables │  │ Research     │ │
│  │  • company_kb │  │ • signal_event│  │ • research_job│ │
│  │  • contact    │  │ • signal_rule │  │ • brief_rev  │ │
│  │  • icp_config │  │ • signal_src  │  │ • draft      │ │
│  │  • pipeline   │  │ • custom_rule │  │ • activity   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                         │
│  pgvector extension (1024-dim embeddings)               │
│  JSONB for flexible schemas (evidence, config, etc.)    │
│  GIN indexes for JSONB array queries                    │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Agent Architecture

### Agent Hierarchy

```
Research Orchestrator (coordinator)
├── Research Planner Agent
│   └── Plans which specialist agents to invoke for a given company
├── Signal Discovery Agent
│   └── Discovers signals from configured sources using tools
├── Competitive Intelligence Agent
│   └── Maps vendor stack, identifies displacement opportunities
├── Hiring Intelligence Agent
│   └── Analyzes job postings for intent signals
├── Executive Intelligence Agent
│   └── Tracks leadership changes, champion movements
├── Tech Stack Intelligence Agent
│   └── Detects technology adoption and migration patterns
├── Procurement Intelligence Agent
│   └── Scans procurement portals, RFP activity
├── Research Synthesis Agent
│   └── Combines all findings into structured brief sections
├── Outreach Strategy Agent
│   └── Generates signal-anchored outreach drafts
└── Confidence Verification Agent
    └── Cross-validates signal claims against multiple sources
```

### Agent Definitions

#### 4.1 Research Planner Agent

**Purpose:** Given a company and signal configuration, determine what research to conduct and in what order.

**Inputs:**
```python
{
    "company": { "name", "domain", "industry", "size", "region" },
    "signal_config": { "signal_types", "custom_signals", "priorities" },
    "existing_signals": [...],  # Already-detected signals to avoid redundancy
    "research_depth": "standard" | "deep" | "comprehensive",
    "budget_constraint": { "max_tool_calls": 50, "max_cost_usd": 0.50 }
}
```

**Outputs:**
```python
{
    "research_plan": [
        {
            "agent": "hiring_intelligence",
            "priority": 1,
            "tools": ["apollo_tool", "linkedin_search_tool"],
            "reason": "Company is 5000+ employees with recent CDO hire — hiring patterns will reveal initiative scope",
            "estimated_cost": 0.08,
            "estimated_time_sec": 15
        },
        ...
    ],
    "parallel_groups": [[0, 1], [2, 3], [4]],  # Which agents can run concurrently
    "skip_reasons": { "procurement_intel": "Company is not publicly listed, no SEC data" }
}
```

**Tools:** None (pure reasoning agent)

**Memory:** Uses company's previous research results to avoid redundant work

#### 4.2 Signal Discovery Agent

**Purpose:** Execute focused signal searches using configured tools and extract structured signals.

**Inputs:**
```python
{
    "company": { ... },
    "signal_types_to_check": ["funding", "hiring_surge", "executive_change"],
    "custom_signal_rules": [...],
    "time_window_days": 90,
    "existing_signals": [...]  # Dedup against these
}
```

**Outputs:**
```python
{
    "signals": [
        {
            "signal_type": "executive_change",
            "subtype": "cdo_appointment",
            "priority": "critical",
            "strength": 92,
            "title": "New CDO appointed — Dr. Priya Nair",
            "summary": "Incoming CDO has track record of consolidating vendor stacks...",
            "evidence": {
                "sources": [
                    { "title": "Meridian Health Press Release", "url": "...", "class": "press_release", "date": "2026-04-28" }
                ],
                "reasoning": "CDO hires at this scale typically trigger vendor reviews within 60-90 days...",
                "corroboration_count": 3
            },
            "confidence": "high",
            "urgency_window_days": 60
        }
    ],
    "no_signal_reasons": {
        "funding": "No funding events found in 90-day window"
    }
}
```

**Tools:** `tavily_tool`, `exa_tool`, `news_sentiment_tool`, `sec_tool`, `web_scraper_tool`, `duckduckgo_tool`

**Collaboration:** Reports findings to Confidence Verification Agent for validation

#### 4.3 Competitive Intelligence Agent

**Purpose:** Map a company's current vendor stack and identify competitive dynamics.

**Inputs:** Company info, detected tech signals, job posting data

**Outputs:**
```python
{
    "current_stack": [
        { "vendor": "Epic", "category": "EHR", "confidence": "high", "evidence": "...", "renewal_date": "Q3 2026" },
        { "vendor": "Tableau", "category": "BI", "confidence": "medium", "evidence": "Job descriptions mention Tableau" }
    ],
    "evaluations_in_progress": [
        { "vendor": "Palantir Health", "evidence": "LinkedIn POC job posting", "confidence": "medium" }
    ],
    "displacement_opportunities": [
        { "category": "BI", "current": "Tableau", "renewal": "Q3 2026", "window": "Now — June 2026" }
    ]
}
```

**Tools:** `web_scraper_tool` (tech detection), `linkedin_search_tool`, `apollo_tool`, `exa_tool`

#### 4.4 Hiring Intelligence Agent

**Purpose:** Analyze job postings for buying intent signals.

**Inputs:** Company name/domain, target role patterns, time window

**Outputs:**
```python
{
    "total_roles_posted": 23,
    "relevant_roles": [
        {
            "title": "VP of Enterprise Architecture",
            "posted_date": "2026-04-25",
            "location": "New York, NY",
            "intent_signals": ["data platform", "vendor evaluation", "cloud migration"],
            "seniority": "VP",
            "department_inference": "Technology / Data"
        }
    ],
    "hiring_velocity": { "30d": 11, "60d": 18, "90d": 23 },
    "department_concentration": { "Data & Platform": 45, "Sales Ops": 23, "Engineering": 32 },
    "intent_keywords_found": ["revenue intelligence", "GTM analytics", "data platform"],
    "signal_strength": 78
}
```

**Tools:** `apollo_tool`, `linkedin_search_tool`, `google_places_tool`

#### 4.5 Executive Intelligence Agent

**Purpose:** Track leadership changes and champion movements.

**Inputs:** Company, known contacts, previous executive snapshot

**Outputs:**
```python
{
    "current_executives": [
        { "name": "Dr. Priya Nair", "title": "CDO", "started": "2026-04", "previous": "Kaiser Permanente", "linkedin": "..." }
    ],
    "changes_detected": [
        { "type": "new_hire", "person": "Dr. Priya Nair", "role": "CDO", "confidence": "high" }
    ],
    "champion_movements": [
        { "person": "Jane Smith", "from": "Acme Corp (your customer)", "to": "Target Corp", "signal_value": "critical" }
    ]
}
```

**Tools:** `find_executives_tool`, `linkedin_search_tool`, `apollo_tool`

#### 4.6 Research Synthesis Agent

**Purpose:** Combine all specialist agent outputs into a structured research brief.

**Inputs:** All specialist agent outputs + company context + user's ICP/offering

**Outputs:** 8 structured brief sections (see Research Brief Architecture)

**Key Behavior:**
- Cross-references findings across agents
- Identifies correlations (e.g., CDO hire + hiring surge = initiative signal)
- Generates "Why Now" and "Recommended Angle" sections using sales strategy reasoning
- Cites all evidence with source attribution
- Assigns confidence per section based on evidence depth

**Tools:** None (pure synthesis agent — receives pre-gathered data)

**Model:** Claude Sonnet 4 (8K output) — the most critical agent for quality

#### 4.7 Outreach Strategy Agent

**Purpose:** Generate signal-anchored outreach drafts.

**Inputs:**
```python
{
    "company": { ... },
    "signal": { ... },         # The triggering signal
    "contact": { ... },        # Target recipient
    "brief_sections": { ... }, # Research brief for context
    "format": "email" | "linkedin",
    "tone": "direct" | "consultative" | "formal" | "casual",
    "voice_profile": "concise" | "consultative" | "formal",
    "user_offering": "..."     # What the user's company does
}
```

**Outputs:**
```python
{
    "subject": "Meridian Health — a thought on the CDO transition",
    "body": "Hi Priya,\n\nI noticed your appointment as CDO at Meridian...",
    "hooks_used": ["CDO appointment", "$40M digital health initiative"],
    "personalization_elements": ["Kaiser Permanente background", "vendor consolidation track record"],
    "banned_phrases_avoided": true,
    "estimated_read_time_sec": 45,
    "variants": [...]  # 2 alternative versions
}
```

**Tools:** None (pure generation agent)

**Anti-hallucination:** Agent MUST only reference facts from the brief/evidence. System prompt includes: "Never invent details about the company or contact. Every claim must be traceable to provided evidence."

#### 4.8 Confidence Verification Agent

**Purpose:** Cross-validate signal claims against multiple sources.

**Inputs:** Candidate signal with initial evidence

**Outputs:**
```python
{
    "verified": true,
    "original_confidence": "medium",
    "adjusted_confidence": "high",
    "corroboration_sources": [
        { "source": "SEC filing", "confirms": true, "detail": "10-K confirms budget allocation" },
        { "source": "LinkedIn", "confirms": true, "detail": "CDO profile updated to Meridian" }
    ],
    "contradictions": [],
    "confidence_reasoning": "Signal corroborated by 3 independent sources across 2 source classes"
}
```

**Tools:** `tavily_tool`, `exa_tool`, `web_scraper_tool`, `sec_tool`

**Trigger:** Only invoked for signals initially rated "medium" or when custom rules require verification

### Agent Collaboration Model

```
User triggers research for Company X
       │
       ▼
Research Planner Agent
  → Analyzes company profile
  → Plans research strategy (which agents, what order, what tools)
  → Returns prioritized execution plan
       │
       ▼
Parallel Execution Group 1:
  ├── Signal Discovery Agent (funding, earnings, press)
  ├── Hiring Intelligence Agent (job postings)
  └── Executive Intelligence Agent (leadership changes)
       │
       ▼
Parallel Execution Group 2:
  ├── Competitive Intelligence Agent (vendor stack)
  ├── Tech Stack Intelligence Agent (technology signals)
  └── Procurement Intelligence Agent (procurement activity)
       │
       ▼
Confidence Verification Agent
  → Cross-validates medium-confidence signals
  → Promotes or downgrades confidence levels
       │
       ▼
Research Synthesis Agent
  → Combines all outputs into structured brief
  → Generates 8 sections with citations
  → Produces "Why Now" and "Recommended Angle"
       │
       ▼
Outreach Strategy Agent (optional, triggered by user)
  → Generates signal-anchored drafts
  → References real evidence from brief
```

---

## 5. Tool Architecture

### New Tools

#### 5.1 Web Intelligence Tool

**Purpose:** Intelligent web crawling with summarization and signal extraction.

```python
@tool
def web_intelligence_tool(
    url: str,
    extraction_focus: str,  # "hiring", "product", "leadership", "tech_stack", "general"
    summarize: bool = True,
    detect_changes: bool = False,
    previous_snapshot_hash: str | None = None,
) -> dict:
    """
    Crawls a URL, extracts structured information, optionally detects changes.
    
    Returns:
        {
            "content_summary": "...",
            "extracted_entities": [...],
            "signals_detected": [...],
            "content_hash": "abc123",
            "changed_sections": [...],  # If detect_changes=True
            "crawl_timestamp": "2026-05-17T10:00:00Z"
        }
    """
```

**Rate Limiting:** 2 req/sec per domain, 100 req/min total
**Caching:** 4-hour TTL for page content, 24-hour for tech stack detection
**Retry:** 3 attempts with exponential backoff (1s, 3s, 9s)

#### 5.2 Change Detection Tool

**Purpose:** Track changes on monitored web pages over time.

```python
@tool
def change_detection_tool(
    url: str,
    previous_content_hash: str,
    change_types: list[str],  # ["content", "structure", "links", "meta"]
) -> dict:
    """
    Compares current page state against stored hash, returns structured diff.
    
    Returns:
        {
            "has_changes": true,
            "change_summary": "3 new job categories added to careers page",
            "added_sections": [...],
            "removed_sections": [...],
            "modified_sections": [...],
            "significance_score": 0.72,
            "new_content_hash": "def456"
        }
    """
```

**Caching:** Stores content hashes in `source_snapshots` table
**Scheduling:** Runs on monitoring schedule (daily/weekly per source)

#### 5.3 Intent Signal Extractor

**Purpose:** NLP-based extraction of buying intent from text.

```python
@tool
def intent_signal_extractor(
    text: str,
    company_context: dict,
    signal_hypotheses: list[str],  # User-defined signal hints
) -> dict:
    """
    Analyzes text for buying intent signals, guided by signal hypotheses.
    
    Returns:
        {
            "intent_signals": [
                {
                    "signal_type": "budget_signal",
                    "evidence_text": "$40M digital health investment earmarked for FY2026",
                    "confidence": 0.89,
                    "intent_category": "active_evaluation",
                    "urgency": "high"
                }
            ],
            "hypothesis_matches": {
                "cloud_migration": { "matched": true, "evidence": "..." },
                "vendor_consolidation": { "matched": false }
            }
        }
    """
```

**Model:** Claude Haiku (fast, cost-efficient for extraction tasks)
**Caching:** Results cached per (text_hash, hypotheses_hash) for 24 hours

#### 5.4 Hiring Signal Detector

```python
@tool
def hiring_signal_detector(
    company_name: str,
    domain: str,
    role_patterns: list[str],  # ["VP*Data*", "*Revenue Intelligence*", "Head of*"]
    time_window_days: int = 90,
) -> dict
```

**Rate Limiting:** Apollo: 5 req/min, LinkedIn: 2 req/min
**Caching:** Job posting data cached 12 hours

#### 5.5 Tech Stack Detector

```python
@tool
def tech_stack_detector(
    domain: str,
    check_methods: list[str] = ["web_headers", "job_descriptions", "github", "builtwith"],
) -> dict
```

**Caching:** Tech stack snapshots cached 7 days (changes are slow)

#### 5.6 Executive Movement Tracker

```python
@tool  
def executive_tracker(
    company_name: str,
    known_executives: list[dict],
    track_departures: bool = True,
    track_arrivals: bool = True,
) -> dict
```

### Tool Observability

Every tool call is instrumented with:
```python
{
    "tool_name": "tavily_tool",
    "call_id": "uuid",
    "company_kb_id": "uuid",
    "research_job_id": "uuid",
    "input_summary": "Searching for 'Meridian Health funding'",
    "output_summary": "3 results found",
    "duration_ms": 1200,
    "cost_estimate_usd": 0.002,
    "cache_hit": false,
    "retry_count": 0,
    "error": null,
    "timestamp": "2026-05-17T10:00:00Z"
}
```

---

## 6. Data Models

### New and Modified Models

#### 6.1 AccountProfile (extends CompanyKnowledgeBase)

```sql
-- New columns on company_knowledge_base
ALTER TABLE company_knowledge_base ADD COLUMN
    status VARCHAR(20) DEFAULT 'monitored',            -- monitored/paused/archived
    owner VARCHAR(255),                                 -- Assigned sales rep
    monitoring_config JSONB DEFAULT '{}',               -- {enabled, frequency_days, signal_types[]}
    last_researched_at TIMESTAMP,
    research_depth VARCHAR(20) DEFAULT 'standard',      -- standard/deep/comprehensive
    signal_count INTEGER DEFAULT 0,                     -- Denormalized
    has_brief BOOLEAN DEFAULT FALSE,
    open_draft_count INTEGER DEFAULT 0,                 -- Denormalized
    tags JSONB DEFAULT '[]'::jsonb;                     -- ["Enterprise", "Healthcare"]
```

#### 6.2 SignalEvent (enhanced)

```sql
CREATE TABLE signal_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_kb_id UUID NOT NULL REFERENCES company_knowledge_base(id),
    signal_type VARCHAR(50) NOT NULL,                   -- funding, hiring_surge, leadership_change, etc.
    signal_subtype VARCHAR(100),                         -- cdo_appointment, series_c, etc.
    signal_category VARCHAR(50),                         -- financial/personnel/product/event/intent
    priority VARCHAR(20) DEFAULT 'medium',               -- critical/high/medium/low
    strength FLOAT DEFAULT 50,                           -- 0-100 signal strength
    confidence VARCHAR(20) DEFAULT 'medium',             -- high/medium/low
    title VARCHAR(500) NOT NULL,
    headline VARCHAR(500),                               -- Source headline
    summary TEXT,                                        -- AI-generated "why this matters"
    evidence JSONB NOT NULL DEFAULT '{}',                -- {sources: [], reasoning: "", corroboration_count: N}
    source_tool VARCHAR(100),
    source_url VARCHAR(1000),
    source_class VARCHAR(100),                           -- press_release, sec_filing, hiring_signal, web_change
    source_date DATE,
    lifecycle VARCHAR(20) DEFAULT 'new',                 -- new/saved/acted_on/dismissed/snoozed
    snoozed_until TIMESTAMP,
    is_auto_generated BOOLEAN DEFAULT FALSE,
    custom_rule_id UUID REFERENCES custom_signal_rules(id),
    custom_rule_name VARCHAR(255),
    detected_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,                                -- Based on signal decay config
    evidence_date DATE,                                  -- When the underlying event occurred
    research_job_id UUID,                                -- Links to the research job that found it
    region VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_signal_company_date ON signal_events(company_kb_id, detected_at DESC);
CREATE INDEX idx_signal_type ON signal_events(signal_type);
CREATE INDEX idx_signal_lifecycle ON signal_events(lifecycle);
CREATE INDEX idx_signal_priority ON signal_events(priority);
CREATE INDEX idx_signal_confidence ON signal_events(confidence);
```

#### 6.3 BriefRevision

```sql
CREATE TABLE brief_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_kb_id UUID NOT NULL REFERENCES company_knowledge_base(id),
    version INTEGER NOT NULL,                            -- 1, 2, 3, ...
    sections JSONB NOT NULL,                             -- [{id, heading, body, bullets, sources, insufficient}]
    word_count INTEGER,
    generated_by VARCHAR(20) DEFAULT 'auto',             -- auto/manual
    trigger_signal_id UUID REFERENCES signal_events(id),
    trigger_signal_headline VARCHAR(500),
    model_id VARCHAR(100),                               -- Which Claude model generated it
    generation_cost_usd FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_brief_company ON brief_revisions(company_kb_id, version DESC);
CREATE UNIQUE INDEX idx_brief_company_version ON brief_revisions(company_kb_id, version);
```

#### 6.4 Draft

```sql
CREATE TABLE drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_kb_id UUID NOT NULL REFERENCES company_knowledge_base(id),
    signal_id UUID REFERENCES signal_events(id),
    contact_id UUID,                                     -- References contact in KB
    format VARCHAR(20) NOT NULL,                         -- email/linkedin
    tone VARCHAR(20) DEFAULT 'direct',                   -- direct/consultative/formal/casual
    voice_profile VARCHAR(20) DEFAULT 'concise',
    subject VARCHAR(500),                                -- Email subject line
    body TEXT NOT NULL,
    hooks_used JSONB DEFAULT '[]',                       -- Signal references used
    status VARCHAR(20) DEFAULT 'in_progress',            -- in_progress/sent/discarded
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_draft_company ON drafts(company_kb_id, created_at DESC);
CREATE INDEX idx_draft_status ON drafts(status);
```

#### 6.5 CustomSignalRule

```sql
CREATE TABLE custom_signal_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    trigger_type VARCHAR(50) NOT NULL,                   -- keyword/hiring_pattern/tech_stack/company_event
    conditions JSONB NOT NULL,                            -- ["cloud migration", "data platform"] or ["Acquisition", "IPO"]
    scope VARCHAR(50) DEFAULT 'monitored',               -- all/monitored/tagged
    scope_tags JSONB DEFAULT '[]',                        -- ["Enterprise", "Healthcare"]
    action VARCHAR(50) DEFAULT 'signal',                  -- signal/signal_brief/notify
    confidence_override VARCHAR(20) DEFAULT 'medium',
    trigger_count INTEGER DEFAULT 0,
    last_triggered_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### 6.6 CustomSignalSource

```sql
CREATE TABLE custom_signal_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    company_kb_id UUID REFERENCES company_knowledge_base(id),  -- NULL = global source
    source_type VARCHAR(50) NOT NULL,                    -- website/careers/blog/press/sec/linkedin/github/rss/reddit/youtube
    url VARCHAR(1000) NOT NULL,
    name VARCHAR(255),
    crawl_frequency VARCHAR(20) DEFAULT 'weekly',        -- daily/weekly/biweekly/monthly
    last_crawled_at TIMESTAMP,
    last_content_hash VARCHAR(64),                        -- SHA256 for change detection
    reliability_score FLOAT DEFAULT 0.5,                  -- 0-1, updated based on signal quality
    freshness_score FLOAT DEFAULT 1.0,                    -- Decays over time since last crawl
    enabled BOOLEAN DEFAULT TRUE,
    crawl_config JSONB DEFAULT '{}',                      -- {selectors, exclude_patterns, etc.}
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_source_next_crawl ON custom_signal_sources(last_crawled_at, crawl_frequency) WHERE enabled = TRUE;
```

#### 6.7 ResearchJob

```sql
CREATE TABLE research_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_kb_id UUID NOT NULL REFERENCES company_knowledge_base(id),
    job_type VARCHAR(50) NOT NULL,                       -- full_research/signal_scan/contact_enrichment/brief_generation
    status VARCHAR(20) DEFAULT 'pending',                -- pending/running/completed/failed
    config JSONB DEFAULT '{}',                            -- Research parameters
    plan JSONB,                                           -- Research Planner output
    progress JSONB DEFAULT '{}',                          -- {stages_completed, current_stage, etc.}
    results JSONB,                                        -- Final aggregated results
    total_tool_calls INTEGER DEFAULT 0,
    total_cost_usd FLOAT DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 6.8 ActivityEvent

```sql
CREATE TABLE activity_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_job_id UUID REFERENCES research_jobs(id),
    company_kb_id UUID REFERENCES company_knowledge_base(id),
    event_type VARCHAR(50) NOT NULL,                     -- research_start/tool_call/signal_detected/section_generated/etc.
    event_category VARCHAR(50),                           -- research/signal/synthesis/contact/outreach
    narrative TEXT NOT NULL,                               -- Human-friendly description
    narrative_detail TEXT,                                 -- Expanded explanation
    technical_detail JSONB,                                -- Tool call data, timing, etc.
    confidence FLOAT,
    milestone BOOLEAN DEFAULT FALSE,                      -- True for major progress points
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_activity_job ON activity_events(research_job_id, created_at);
CREATE INDEX idx_activity_company ON activity_events(company_kb_id, created_at DESC);
```

#### 6.9 SourceSnapshot (for change detection)

```sql
CREATE TABLE source_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES custom_signal_sources(id),
    content_hash VARCHAR(64) NOT NULL,
    content_summary TEXT,
    extracted_signals JSONB DEFAULT '[]',
    crawled_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_snapshot_source ON source_snapshots(source_id, crawled_at DESC);
```

### Signal Configuration Schema

```python
# Signal Hypothesis Configuration (stored in tracking_list.signal_hints)
{
    "budget_range": {"min": 500000, "max": 5000000, "currency": "USD"},
    "urgency_level": "high",  # high/medium/low
    "custom_buying_signals": [
        "cloud migration",
        "vendor consolidation",
        "data platform evaluation"
    ],
    "target_initiatives": [
        "digital transformation",
        "AI/ML adoption",
        "customer data platform"
    ],
    "strategic_priorities": [
        "operational efficiency",
        "customer experience",
        "cost reduction"
    ],
    "business_pain_indicators": [
        "data silos",
        "manual reporting",
        "compliance gaps"
    ],
    "technology_interests": ["Snowflake", "Databricks", "dbt"],
    "expansion_indicators": ["new office", "international growth"],
    "hiring_indicators": {
        "role_patterns": ["VP*Data*", "*Revenue Intelligence*"],
        "department_focus": ["Data", "Analytics", "Platform Engineering"],
        "velocity_threshold": 10  # roles per 30 days
    },
    "compliance_indicators": ["SOC 2", "HIPAA", "GDPR", "FedRAMP"],
    "target_roles": ["CTO", "CDO", "VP Engineering", "VP Data"]
}
```

### Signal Ontology

```python
SIGNAL_ONTOLOGY = {
    "financial": {
        "funding": {"half_life_days": 2, "cold_days": 14, "weight": 1.0},
        "earnings_report": {"half_life_days": 1, "cold_days": 7, "weight": 0.7},
        "budget_disclosure": {"half_life_days": 7, "cold_days": 30, "weight": 0.9},
    },
    "personnel": {
        "leadership_change": {"half_life_days": 7, "cold_days": 30, "weight": 1.0},
        "champion_job_change": {"half_life_days": 7, "cold_days": 30, "weight": 1.2},
        "hiring_surge": {"half_life_days": 14, "cold_days": 60, "weight": 0.8},
    },
    "product": {
        "product_launch": {"half_life_days": 3, "cold_days": 21, "weight": 0.6},
        "tech_adoption": {"half_life_days": 30, "cold_days": 120, "weight": 0.7},
        "tech_removal": {"half_life_days": 3, "cold_days": 14, "weight": 0.9},
    },
    "event": {
        "press_mention": {"half_life_days": 3, "cold_days": 14, "weight": 0.4},
        "partnership": {"half_life_days": 7, "cold_days": 30, "weight": 0.6},
        "expansion": {"half_life_days": 14, "cold_days": 60, "weight": 0.7},
        "web_change": {"half_life_days": 7, "cold_days": 30, "weight": 0.3},
        "sec_filing": {"half_life_days": 3, "cold_days": 21, "weight": 0.8},
    },
    "intent": {
        "budget_signal": {"half_life_days": 14, "cold_days": 60, "weight": 1.0},
        "urgency_signal": {"half_life_days": 7, "cold_days": 30, "weight": 0.9},
        "custom_signal": {"half_life_days": 14, "cold_days": 60, "weight": 0.8},
    }
}
```

---

## 7. Event & Activity Feed Architecture

### Research Narrative Engine

Transforms raw tool/agent events into human-friendly narrations:

```python
class ActivityNarrator:
    """Converts technical events into user-friendly research narration."""
    
    TEMPLATES = {
        "tool_call.tavily_search": {
            "narrative": "Searching for {query_summary} across news and press sources",
            "detail": "Querying Tavily API for '{query}' with {result_count} results",
        },
        "tool_call.apollo_search": {
            "narrative": "Looking up hiring activity and employee data for {company_name}",
        },
        "signal.detected": {
            "narrative": "Detected {signal_type_human}: {signal_title}",
            "detail": "Confidence: {confidence} | Strength: {strength}/100 | Source: {source_class}",
        },
        "synthesis.section_started": {
            "narrative": "Generating research brief section: {section_name}",
        },
        "correlation.found": {
            "narrative": "Correlating {signal_a} with {signal_b} — {correlation_insight}",
        },
        "verification.complete": {
            "narrative": "Verified signal against {source_count} independent sources — confidence {direction} to {confidence}",
        },
    }
    
    def narrate(self, event: dict) -> ActivityEvent:
        """Convert raw event to narrated ActivityEvent."""
```

### Activity Translation Layer

```python
SIGNAL_TYPE_HUMAN = {
    "funding": "new funding activity",
    "hiring_surge": "rapid expansion in hiring",
    "leadership_change": "executive leadership change",
    "champion_job_change": "former champion at new company",
    "tech_adoption": "new technology adoption",
    "product_launch": "product or feature launch",
    "earnings_report": "earnings disclosure",
    "press_mention": "press coverage",
    "partnership": "strategic partnership",
    "expansion": "geographic or operational expansion",
    "web_change": "website content update",
    "sec_filing": "regulatory filing",
    "budget_signal": "budget indicator",
    "urgency_signal": "urgency indicator",
    "custom_signal": "custom signal match",
}
```

### Streaming Update Model

```python
# SSE event types for research progress
class ResearchStreamEvent:
    """Events streamed to frontend during research."""
    
    # Research lifecycle
    RESEARCH_STARTED = "research_started"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    RESEARCH_COMPLETED = "research_completed"
    
    # Activity narration
    ACTIVITY = "activity"                    # Human-friendly narration
    ACTIVITY_MILESTONE = "activity_milestone" # Major progress point
    
    # Signal events
    SIGNAL_DETECTED = "signal_detected"
    SIGNAL_VERIFIED = "signal_verified"
    
    # Brief events
    BRIEF_SECTION_STARTED = "brief_section_started"
    BRIEF_SECTION_COMPLETE = "brief_section_complete"
    BRIEF_READY = "brief_ready"
    
    # Contact events
    CONTACT_FOUND = "contact_found"
    CONTACT_ENRICHMENT_COMPLETE = "contact_enrichment_complete"
    
    # Error
    ERROR = "error"
```

---

## 8. Research Brief Architecture

### Brief Section Schema

```python
class BriefSection:
    id: str                          # overview, org, signals, competitive, tech, budget, why-now, angle
    heading: str
    body: str                        # Markdown with inline citations [1], [2]
    bullets: list[str] | None
    sources: list[BriefSectionSource] | None
    insufficient: bool = False       # True when not enough data
    confidence: float | None         # 0-1 section confidence

class BriefSectionSource:
    label: str                       # "Meridian Health FY2025 Annual Report"
    source_class: str                # "SEC filing", "Press release", "Hiring signal", "Web change"
    url: str | None                  # Link to original source
    date: str | None
```

### Brief Generation Flow

```
1. Research Synthesis Agent receives all specialist outputs
2. For each section:
   a. Select relevant findings from specialist agents
   b. Generate section body with inline citations
   c. Extract key bullets
   d. Compile source list
   e. Assess confidence based on evidence depth
   f. Stream section to frontend via SSE
3. Generate "Why Now" section (cross-cutting analysis)
4. Generate "Recommended Angle" section (sales strategy)
5. Compute word count, save BriefRevision
6. If triggered by signal, store trigger_signal_id
```

### Brief Versioning Strategy

- Briefs are **append-only** — never modified, new versions created
- Auto-regeneration triggered by:
  - High-confidence signal detected for the account
  - User clicks "Regenerate"
  - Scheduled monitoring finds significant changes
- Each version tracks: trigger signal, word count, generation cost, model ID
- Frontend shows revision dropdown with version history

### Citation UX

Inline citations `[1]` in brief body text:
- Click a citation → highlights corresponding source chip below the section
- Source chips show: label, source class (monospace), external link
- Highlight uses accent ring + background change, auto-dismisses after 1.6s
- Sources without URLs render without link styling

---

## 9. Signal Intelligence Architecture

### Weak Signal Correlation Engine

```python
class SignalCorrelator:
    """Identifies meaningful patterns across multiple weak signals."""
    
    CORRELATION_RULES = [
        {
            "name": "Initiative Signal",
            "pattern": ["leadership_change", "hiring_surge"],
            "window_days": 30,
            "boost_factor": 1.5,
            "narrative": "Leadership change + hiring surge suggests new initiative planning"
        },
        {
            "name": "Vendor Evaluation Window",
            "pattern": ["leadership_change", "tech_adoption"],
            "window_days": 60,
            "boost_factor": 1.4,
            "narrative": "New leader + tech changes = likely vendor evaluation period"
        },
        {
            "name": "Budget-Backed Initiative",
            "pattern": ["funding", "hiring_surge"],
            "window_days": 90,
            "boost_factor": 1.6,
            "narrative": "Fresh funding + aggressive hiring = active build-out phase"
        },
        {
            "name": "Competitive Displacement Opportunity",
            "pattern": ["tech_removal", "hiring_surge"],
            "window_days": 30,
            "boost_factor": 1.8,
            "narrative": "Competitor product dropped + new hires = active replacement search"
        },
    ]
    
    def correlate(self, signals: list[SignalEvent]) -> list[CorrelationResult]:
        """Find meaningful patterns across signals."""
```

### Signal Heat Score Computation

```python
def compute_signal_heat(signals: list[SignalEvent], config: SignalOntology) -> float:
    """
    Composite signal heat score combining multiple signals with decay.
    
    Formula: heat = sum(weight * strength * decay(age) * correlation_boost)
    
    Where:
    - weight: Signal type weight from ontology
    - strength: 0-100 signal strength
    - decay: exp(-ln(2) * age_days / half_life_days)
    - correlation_boost: 1.0 base, higher when correlated with other signals
    """
    heat = 0.0
    correlations = SignalCorrelator().correlate(signals)
    
    for signal in signals:
        if signal.is_dismissed or signal.is_archived:
            continue
        
        type_config = config[signal.signal_category][signal.signal_type]
        age_days = (datetime.utcnow() - signal.detected_at).days
        
        # Skip cold signals
        if age_days > type_config["cold_days"]:
            continue
        
        decay = math.exp(-math.log(2) * age_days / type_config["half_life_days"])
        boost = get_correlation_boost(signal, correlations)
        
        heat += type_config["weight"] * (signal.strength / 100) * decay * boost
    
    return min(heat * 100, 100)  # Normalize to 0-100
```

### Confidence Scoring Model

Multi-factor confidence assessment:

```python
def assess_confidence(signal: dict) -> str:
    """
    Determines signal confidence based on:
    1. Source authority (SEC filing > press release > blog post > single web change)
    2. Corroboration count (3+ sources = high, 1-2 = medium, 1 = low)
    3. Source recency (within 7 days = boost, >30 days = penalty)
    4. Source class diversity (multiple source types > single type)
    
    Returns: "high", "medium", or "low"
    """
    score = 0.0
    
    # Source authority
    SOURCE_AUTHORITY = {
        "sec_filing": 0.9, "press_release": 0.8, "earnings_call": 0.85,
        "news_article": 0.6, "hiring_signal": 0.7, "web_change": 0.3,
        "social_media": 0.2, "forum": 0.15
    }
    score += SOURCE_AUTHORITY.get(signal["source_class"], 0.3)
    
    # Corroboration
    corroboration = signal["evidence"].get("corroboration_count", 1)
    if corroboration >= 3: score += 0.3
    elif corroboration >= 2: score += 0.15
    
    # Recency
    age_days = (datetime.utcnow().date() - signal["source_date"]).days
    if age_days <= 7: score += 0.1
    elif age_days > 30: score -= 0.1
    
    # Source diversity
    source_classes = set(s["class"] for s in signal["evidence"]["sources"])
    if len(source_classes) >= 2: score += 0.15
    
    if score >= 0.8: return "high"
    if score >= 0.5: return "medium"
    return "low"
```

### Temporal Analysis

```python
class TemporalAnalyzer:
    """Analyzes signal trends over time."""
    
    def detect_acceleration(self, signals: list, window_days: int = 30) -> dict:
        """Detect if signal frequency is accelerating."""
        
    def detect_pattern(self, signals: list) -> list:
        """Identify recurring patterns (e.g., quarterly earnings → hiring surge)."""
        
    def predict_window(self, signal: SignalEvent) -> dict:
        """Estimate optimal action window based on signal type and history."""
        # E.g., "CDO appointment → 60-90 day vendor review window"
```

---

## 10. Contact Enrichment Architecture

### Async Enrichment Workflow

```
User triggers "Enrich Contacts" for a company
       │
       ▼
Create ResearchJob (type=contact_enrichment)
       │
       ▼
Executive Intelligence Agent
  ├── Apollo API: Search for company contacts by title patterns
  ├── LinkedIn Search: Find decision makers
  ├── Find Executives Tool: Identify C-suite and VPs
  └── Cross-reference with brief's org section
       │
       ▼
For each discovered contact:
  ├── Enrich email via Hunter/Apollo
  ├── Find LinkedIn profile
  ├── Infer role and influence level
  ├── Determine if EU resident (for GDPR)
  └── Stream CONTACT_FOUND event to frontend
       │
       ▼
Store in CompanyKnowledgeBase.best_known_contacts (JSONB)
       │
       ▼
Emit CONTACT_ENRICHMENT_COMPLETE
```

### Contact Schema

```python
{
    "contacts": [
        {
            "id": "uuid",
            "name": "Dr. Priya Nair",
            "title": "Chief Data Officer",
            "email": "pnair@meridianhealth.com",
            "linkedin_url": "https://linkedin.com/in/priyanair",
            "phone": null,
            "is_primary": true,
            "is_eu_resident": false,
            "influence_level": "decision_maker",  # decision_maker/influencer/champion/blocker/end_user
            "department": "Data & Analytics",
            "started_date": "2026-04",
            "previous_company": "Kaiser Permanente",
            "enrichment_source": "apollo + linkedin",
            "enrichment_confidence": 0.92,
            "enriched_at": "2026-05-17T10:00:00Z"
        }
    ]
}
```

### Enrichment Progress UX States

```
┌──────────────────────────────────────┐
│ Contacts (4)                          │
│ ┌──────────────────────────────────┐ │
│ │ ✓ Dr. Priya Nair · CDO          │ │  ← Enriched
│ │ ✓ James Whitfield · SVP Tech Ops │ │  ← Enriched
│ │ ⟳ Rachel Osei · VP Procurement  │ │  ← Enriching (spinner)
│ │ ○ Dr. Marcus Chen · CMO         │ │  ← Pending
│ └──────────────────────────────────┘ │
│ Progress: 2/4 contacts enriched       │
│ [████████░░░░░░░] 50%                │
└──────────────────────────────────────┘
```

---

## 11. Outreach Generation Architecture

### Draft Generation Flow

```
User clicks "Draft email" on a signal or account
       │
       ▼
DraftDrawer opens with pre-populated context:
  - Account info from KB
  - Signal context (if triggered from signal)
  - Contact list from enrichment
  - Research brief sections for context
       │
       ▼
Outreach Strategy Agent generates draft:
  - References ONLY facts from brief/evidence
  - Anchors to triggering signal
  - Applies tone + voice profile
  - Generates subject line (email)
  - Produces 2 variants
       │
       ▼
User reviews in DraftDrawer:
  - Edit body + subject
  - Change contact, format, tone
  - Regenerate for alternative variant
  - Copy to clipboard
  - Mark as sent (moves signal to "acted_on")
```

### Outreach Templates

```python
OUTREACH_TEMPLATES = {
    "congratulate_funding": {
        "hook_pattern": "I noticed {company} recently {event_summary}",
        "bridge": "Post-close is typically when teams begin evaluating...",
        "cta": "Would a 20-minute conversation be useful?"
    },
    "leadership_change_intro": {
        "hook_pattern": "I saw your appointment as {title} at {company}",
        "bridge": "Leaders in your position typically spend the first 90 days...",
        "cta": "Happy to share a quick framework — no sales deck, just context."
    },
    "competitive_displacement": {
        "hook_pattern": "I noticed {company} has been evaluating alternatives to {competitor}",
        "bridge": "Teams making this transition often find that...",
        "cta": "I have a couple of specific examples I think would be relevant."
    },
    "hiring_signal": {
        "hook_pattern": "I noticed {company} is building out the {department} team",
        "bridge": "Companies at your stage with similar hiring patterns...",
        "cta": "Would you be open to a short call this week?"
    }
}
```

### Anti-Hallucination Safeguards

1. **Evidence-only generation:** System prompt instructs: "Every claim about the company MUST reference data from the provided brief or signal evidence. Never invent facts."
2. **Banned phrases:** ["synergy", "reach out", "circle back", "touch base", "game changer", "leverage", "paradigm shift", "disruptive", "bandwidth", "low-hanging fruit"]
3. **Stale signal warning:** If hook signal is >7 days old, show amber warning
4. **Edited draft notice:** If user modifies AI-generated text, show info banner
5. **Character limits:** LinkedIn 300 chars, Email 2000 chars with visual counter

---

## 12. Custom Signal Sources Architecture

### Source Connector Framework

```python
class SourceConnector(ABC):
    """Base class for all source connectors."""
    
    @abstractmethod
    async def crawl(self, source: CustomSignalSource) -> CrawlResult: ...
    
    @abstractmethod
    async def detect_changes(self, source: CustomSignalSource, previous: SourceSnapshot) -> ChangeResult: ...
    
    @abstractmethod
    async def extract_signals(self, content: str, company: dict, hypotheses: list[str]) -> list[dict]: ...

class WebsiteConnector(SourceConnector): ...    # Generic website crawling
class CareersPageConnector(SourceConnector): ... # Job posting extraction
class BlogConnector(SourceConnector): ...        # Blog post monitoring
class PressReleaseConnector(SourceConnector): ... # Press release parsing
class SECFilingConnector(SourceConnector): ...   # SEC filing analysis
class LinkedInConnector(SourceConnector): ...    # LinkedIn page monitoring
class GitHubConnector(SourceConnector): ...      # GitHub org activity
class RSSConnector(SourceConnector): ...         # RSS feed monitoring
class RedditConnector(SourceConnector): ...      # Reddit discussion tracking
class YouTubeConnector(SourceConnector): ...     # YouTube channel monitoring
class ProcurementConnector(SourceConnector): ... # Procurement portal scanning
```

### Crawling Strategy

```python
class CrawlScheduler:
    """Manages crawl scheduling with priority and rate limiting."""
    
    async def get_due_sources(self) -> list[CustomSignalSource]:
        """Returns sources due for crawling based on frequency config."""
        
    async def crawl_source(self, source: CustomSignalSource):
        """
        1. Fetch current content
        2. Compute content hash
        3. If hash differs from stored: detect changes
        4. Extract signals from changed content
        5. Store new snapshot
        6. Update source freshness_score
        7. If signals found: emit signal events
        """
```

### Change Detection Strategy

```python
class ChangeDetector:
    """Detects meaningful changes between page versions."""
    
    def detect(self, old_content: str, new_content: str) -> ChangeResult:
        """
        Returns:
        - added_sections: New content blocks
        - removed_sections: Removed content blocks  
        - modified_sections: Changed content blocks
        - significance_score: 0-1 (filters out minor CSS/layout changes)
        """
```

**Significance Filtering:**
- Ignore: CSS/JS changes, minor formatting, footer/header updates
- Flag: New job postings, new product mentions, leadership announcements
- Semantic diffing via embeddings for meaning-level change detection

### Source Reliability Scoring

```python
def update_reliability(source: CustomSignalSource, signal_outcomes: list[dict]):
    """
    Updates source reliability based on signal quality:
    - Signals that were acted on → increase reliability
    - Signals that were dismissed → decrease reliability
    - Signals corroborated by other sources → increase
    - False positive signals → decrease significantly
    
    Formula: reliability = (acted + corroborated) / (total + dismissed * 2)
    """
```

---

## 13. AI Orchestration Strategy

### Model Selection per Task

| Task | Model | Reasoning |
|------|-------|-----------|
| Research Planning | Claude Sonnet 4 | Complex reasoning, cost-efficient |
| Signal Discovery | Claude Sonnet 4 | Good extraction + reasoning |
| Confidence Verification | Claude Sonnet 4 | Cross-reference analysis |
| Research Synthesis (Brief) | Claude Sonnet 4 | Long-form generation with citations |
| Outreach Generation | Claude Sonnet 4 | Creative + structured output |
| Activity Narration | Claude Haiku 4.5 | Simple template-based generation |
| Intent Signal Extraction | Claude Haiku 4.5 | Fast extraction task |
| Change Summarization | Claude Haiku 4.5 | Summarization task |
| Co-pilot Chat | Claude Sonnet 4 | Interactive, context-aware |
| Pipeline Lead Gen | Claude Sonnet 4 | (existing) |

### Orchestration Flow

```
Research Orchestrator (Python service, not an agent)
  │
  ├── Calls Research Planner Agent (1 LLM call)
  │     → Returns execution plan
  │
  ├── Executes plan stages (parallel where possible)
  │     ├── Stage 1: [Signal Discovery, Hiring Intel, Executive Intel] — parallel
  │     ├── Stage 2: [Competitive Intel, Tech Stack Intel] — parallel
  │     └── Stage 3: Confidence Verification (sequential, needs Stage 1-2 outputs)
  │
  ├── Calls Research Synthesis Agent (1-2 LLM calls)
  │     → Returns structured brief sections
  │
  └── Optionally: Outreach Strategy Agent (1 LLM call)
        → Returns draft outreach

Total LLM calls per full research: 4-8
Total tool calls: 15-30
Estimated cost: $0.15-0.40 per company
Estimated time: 30-90 seconds
```

### Retry Strategy

```python
RETRY_CONFIG = {
    "llm_calls": {
        "max_retries": 3,
        "backoff": "exponential",
        "initial_delay_ms": 1000,
        "max_delay_ms": 30000,
        "retry_on": ["rate_limit", "timeout", "server_error"]
    },
    "tool_calls": {
        "max_retries": 2,
        "backoff": "exponential",
        "initial_delay_ms": 500,
        "max_delay_ms": 10000,
        "retry_on": ["timeout", "server_error", "rate_limit"]
    },
    "crawl_operations": {
        "max_retries": 3,
        "backoff": "linear",
        "initial_delay_ms": 2000,
        "retry_on": ["timeout", "dns_error", "connection_error"]
    }
}
```

---

## 14. Caching Strategy

### Cache Layers

```
Layer 1: In-Memory (Python dict, per-process)
├── Signal ontology configuration (static, loaded at startup)
├── Signal decay configs (static)
├── Tool registry metadata (static)
└── TTL: Application lifetime

Layer 2: Application Cache (Redis or in-memory with TTL)
├── Company research results (4-hour TTL)
├── Tool call results by (tool, input_hash) (varies by tool)
├── Signal heat scores per company (recomputed on change + 1-hour TTL)
├── Brief section content (until new version generated)
├── Source content hashes (24-hour TTL)
└── Notification unread counts (30-second TTL)

Layer 3: Database (PostgreSQL)
├── All persistent state
├── KB records (golden, indefinite)
├── Signal events (retained, archived after cold period)
├── Brief revisions (retained indefinitely)
└── Source snapshots (retained 90 days)
```

### Tool-Specific Cache TTLs

```python
TOOL_CACHE_TTL = {
    "apollo_tool": timedelta(hours=12),       # Contact data changes slowly
    "linkedin_search_tool": timedelta(hours=6),
    "tavily_tool": timedelta(hours=4),         # News changes frequently
    "exa_tool": timedelta(hours=4),
    "news_sentiment_tool": timedelta(hours=2), # News is time-sensitive
    "sec_tool": timedelta(days=7),             # SEC filings are permanent
    "web_scraper_tool": timedelta(hours=4),    # Web content changes moderately
    "find_executives_tool": timedelta(days=1), # Leadership changes rarely
    "google_places_tool": timedelta(days=7),   # Physical locations change slowly
    "simfin_tool": timedelta(days=1),          # Financial data changes daily
    "fmp_tool": timedelta(days=1),
}
```

---

## 15. Memory Strategy

### Company Knowledge Graph

The `CompanyKnowledgeBase` table serves as the persistent memory layer:

```python
# KB stores cumulative intelligence per company
{
    "best_known_name": "Meridian Health Systems",
    "best_known_domain": "meridianhealth.com",
    "best_known_industry": "Healthcare",
    "best_known_size": "5000-10000",
    "best_known_revenue": "$2.1B",
    "best_known_contacts": [...],
    "best_known_tech_stack": ["Epic", "Tableau", "AWS", "Python", "Kafka"],
    "embedding": [1024-dim vector],  # For semantic search
    
    # Research memory
    "last_research_job_id": "uuid",
    "last_brief_version": 3,
    "signal_history_summary": "2 high-priority signals in last 30 days...",
    "vendor_stack_snapshot": {...},  # Last known vendor landscape
    "executive_snapshot": [...],     # Last known leadership team
}
```

### Agent Memory

Each specialist agent has access to:
1. **Company's KB record** — accumulated facts
2. **Previous research results** — avoid redundant tool calls
3. **Signal history** — build on existing intelligence, don't re-discover
4. **User's signal hints** — guide research focus

Memory is NOT conversation-based (no long-term chat memory for agents). Each research job starts fresh with full context injected.

### Long-Term Signal Tracking

```python
# Signal events are retained indefinitely (archived after cold period)
# This enables:
# 1. Trend analysis: "Meridian has had 3 leadership changes in 12 months"
# 2. Pattern detection: "Every Q1, this company posts VP-level roles"
# 3. Correlation history: "Last funding + hiring surge led to $10M contract"
# 4. Feedback loops: "Signals of type X at companies like Y have 18% response rate"
```

---

## 16. Observability Strategy

### Metrics

```python
# Research Performance
research_jobs_total                     # Counter: total research jobs
research_job_duration_seconds           # Histogram: time per job
research_job_tool_calls                 # Histogram: tool calls per job
research_job_cost_usd                   # Histogram: cost per job
research_job_signals_detected           # Histogram: signals found per job

# Signal Quality
signals_detected_total                  # Counter by type, confidence
signals_acted_on_total                  # Counter: user took action
signals_dismissed_total                 # Counter: user dismissed
signal_heat_score_distribution          # Histogram: heat score distribution

# Brief Quality
briefs_generated_total                  # Counter
brief_generation_duration_seconds       # Histogram
brief_word_count                        # Histogram

# Tool Performance
tool_call_duration_seconds              # Histogram by tool
tool_call_cache_hit_ratio               # Gauge by tool
tool_call_error_rate                    # Gauge by tool
tool_call_cost_usd                      # Counter by tool

# User Engagement
outreach_drafts_created_total           # Counter
outreach_drafts_sent_total              # Counter
outreach_drafts_copied_total            # Counter
brief_views_total                       # Counter
signal_feed_views_total                 # Counter
```

### Structured Logging

```python
# Every significant operation logs:
{
    "event": "signal_detected",
    "company_kb_id": "uuid",
    "signal_type": "leadership_change",
    "confidence": "high",
    "research_job_id": "uuid",
    "tool_chain": ["tavily_tool", "exa_tool", "web_scraper_tool"],
    "total_duration_ms": 4500,
    "total_cost_usd": 0.012,
    "timestamp": "2026-05-17T10:00:00Z"
}
```

---

## 17. Scalability Strategy

### Current Architecture (Phase 1)
- Single FastAPI process with thread pool executor
- PostgreSQL with pgvector
- SSE streaming for real-time updates
- In-memory caching

### Scaled Architecture (Phase 2+)
```
Load Balancer (ALB)
├── FastAPI Workers (2-4 instances, ECS Fargate)
│   └── Async request handling
├── Research Workers (1-2 instances, ECS Fargate)
│   └── Long-running research jobs
├── Redis (ElastiCache)
│   └── Shared cache + pub/sub for SSE fan-out
├── PostgreSQL (RDS, Multi-AZ)
│   └── pgvector + read replicas
└── CloudWatch Events
    └── Scheduled monitoring triggers
```

### Bottleneck Mitigation
- **External API rate limits:** Per-tool rate limiters, request queuing, burst absorption
- **LLM latency:** Parallel agent execution, streaming responses, Haiku for fast tasks
- **Database:** Connection pooling, read replicas, materialized views for dashboards
- **SSE scaling:** Redis pub/sub for multi-instance SSE fan-out

---

## 18. Cost Optimization Strategy

### Per-Company Cost Breakdown

| Operation | Estimated Cost | Notes |
|-----------|---------------|-------|
| Full research (first time) | $0.15 - $0.40 | 4-8 LLM calls + 15-30 tool calls |
| Signal monitoring scan | $0.02 - $0.05 | Direct tool calls, no LLM |
| Brief generation | $0.03 - $0.08 | 1-2 Sonnet calls |
| Outreach draft | $0.01 - $0.03 | 1 Sonnet call |
| Contact enrichment | $0.05 - $0.15 | Apollo + LinkedIn API calls |

### Optimization Levers

1. **KB-first enrichment** — Known companies skip API calls (near-free)
2. **Aggressive caching** — Tool results cached 4-24 hours
3. **Haiku for extraction** — Use cheapest model for simple tasks
4. **Signal detection without LLM** — Direct tool calls for standard signal types
5. **Parallel execution** — Reduces wall-clock time, same cost
6. **Smart scheduling** — Monitor high-value companies more frequently
7. **Incremental research** — Only re-research sections with new evidence

### Monthly Cost Estimates

| Scale | Companies | Monthly Est. |
|-------|-----------|-------------|
| Startup | 100 tracked | $50-100 |
| Growth | 500 tracked | $200-400 |
| Enterprise | 2000 tracked | $800-1500 |

---

## 19. Security Considerations

### Data Protection
- All API keys stored in AWS Secrets Manager (existing pattern)
- Contact PII encrypted at rest (PostgreSQL TDE)
- EU resident flagging for GDPR compliance
- GDPR banner on contacts with EU residents
- Audit trail for all data access

### Access Control
- Role-based access (existing RBAC system)
- Admin-only access to tool configuration
- Per-user tracking lists (no cross-user data leakage)
- API rate limiting per user

### AI Safety
- Anti-hallucination safeguards in outreach generation
- Evidence-only generation policy
- Banned phrase detection
- Human review step before any outreach is sent
- No auto-sending — all outreach is copy/paste

### External API Security
- API keys never exposed to frontend
- All external calls proxied through backend
- Request/response logging for audit
- IP allowlisting where supported

---

## 20. Phased Implementation Roadmap

### Phase 1: Foundation (Weeks 1-3)
**Goal:** Core signal intelligence UX with Quantiv-grade design

| Week | Deliverables |
|------|-------------|
| 1 | Design system components (Badge, Button, Card, Banner, EmptyState, Skeleton) |
| 1 | New navigation sidebar (Main/Research/Workspace/Admin groups) |
| 1 | Database migrations (signal_events enhanced, brief_revisions, drafts, custom_signal_rules, activity_events) |
| 2 | Signal Feed page (master-detail layout, filters, tabs, detail pane) |
| 2 | Signal state context (lifecycle management: new/saved/acted_on/dismissed/snoozed) |
| 2 | Activity Narrator service (event → human narration) |
| 3 | Accounts listing page (Quantiv-style table with filters, ICP fit badges) |
| 3 | Account Profile page (header card + 5 tabs: Overview, Signals, Brief, Drafts, Contacts) |
| 3 | Signal timeline component (vertical timeline with confidence dots) |

### Phase 2: Research Intelligence (Weeks 4-6)
**Goal:** Deep AI research with streaming briefs

| Week | Deliverables |
|------|-------------|
| 4 | Research Planner Agent + Research Orchestrator service |
| 4 | Research job management (create, stream progress, complete) |
| 4 | SSE streaming for research progress |
| 5 | Research Synthesis Agent (8-section brief generation) |
| 5 | Research Brief page (TOC sidebar, progressive streaming, citations) |
| 5 | Brief revision system (versioning, revision dropdown) |
| 6 | Signal Discovery Agent (detect signals from research data) |
| 6 | Confidence Verification Agent |
| 6 | Signal heat score computation with decay |

### Phase 3: Outreach & Contacts (Weeks 7-9)
**Goal:** Signal-anchored outreach and async contact enrichment

| Week | Deliverables |
|------|-------------|
| 7 | Draft Drawer (global overlay, tone/voice controls, format toggle) |
| 7 | Outreach Strategy Agent (signal-anchored draft generation) |
| 7 | Draft persistence + lifecycle (in_progress/sent/discarded) |
| 8 | Contact enrichment service (async Apollo + LinkedIn) |
| 8 | Contacts tab on Account Profile (table, enrichment progress, EU warnings) |
| 8 | Executive Intelligence Agent |
| 9 | Quick actions on signals (Draft outreach, Save, Dismiss, Snooze) |
| 9 | Notification system (bell icon, unread count, drawer) |
| 9 | Custom Signal Rules page (rule CRUD, trigger types, scopes, actions) |

### Phase 4: Custom Sources & Advanced Intelligence (Weeks 10-12)
**Goal:** Custom signal sources, correlation, and monitoring

| Week | Deliverables |
|------|-------------|
| 10 | Custom signal source management (CRUD, source types) |
| 10 | Source connector framework (website, careers, blog, press connectors) |
| 10 | Change detection engine |
| 11 | Competitive Intelligence Agent |
| 11 | Hiring Intelligence Agent |
| 11 | Tech Stack Intelligence Agent |
| 11 | Signal Correlation Engine (pattern detection across signals) |
| 12 | Scheduled monitoring service (cron-triggered) |
| 12 | Dashboard integration (stats strip, top signals, drafts) |
| 12 | Co-pilot context for new pages |

### Phase 5: Polish & Scale (Weeks 13-14)
**Goal:** Enterprise readiness

| Week | Deliverables |
|------|-------------|
| 13 | Ingest pipeline improvements (signal hypothesis configuration) |
| 13 | Activity feed verbosity levels (Summary/Detailed/Technical) |
| 13 | Export capabilities (brief PDF, signal report) |
| 14 | Performance optimization (caching, parallel execution) |
| 14 | Observability (metrics, structured logging) |
| 14 | End-to-end testing of all workflows |

### Future Phases
- **Phase 6:** Champion tracking, playbooks, feedback-driven score adjustment
- **Phase 7:** Stakeholder mapping, list comparison, bulk re-scoring
- **Phase 8:** Email digest, CRM integration, team collaboration
- **Phase 9:** ML-based signal weight optimization from outcome data

---

## 21. Tech Stack & APIs

### Backend
- **Framework:** FastAPI (async, existing)
- **Database:** PostgreSQL 16 + pgvector (existing)
- **ORM:** SQLAlchemy async + Alembic (existing)
- **AI:** AWS Bedrock (Claude Sonnet 4, Claude Haiku 4.5) via Strands SDK (existing)
- **Embeddings:** AWS Bedrock Titan Embed Text v2 (existing)
- **Cache:** In-memory (Phase 1), Redis/ElastiCache (Phase 2)
- **Queue:** asyncio.to_thread (Phase 1), arq/Redis (Phase 2)
- **Scheduling:** CloudWatch Events → secured endpoint (existing pattern)

### Frontend
- **Framework:** React 19 + TypeScript (existing)
- **Build:** Vite (existing)
- **UI Components:** Ant Design 6 (existing base) + custom Quantiv-style components
- **Styling:** TailwindCSS 4 (existing)
- **Icons:** Lucide React (Quantiv pattern)
- **State:** React Query (TanStack) for server state, Context for UI state
- **Routing:** React Router (existing)
- **Charts:** Recharts (existing)
- **Markdown:** react-markdown + remark-gfm (existing, for briefs)

### External APIs
- **Apollo** — Contact data, job postings, company enrichment
- **Exa** — AI-powered web search
- **Tavily** — News and web search
- **Hunter** — Email verification
- **Lusha** — Contact enrichment
- **SimFin / FMP** — Financial data
- **Google Places** — Location data
- **SEC EDGAR** — SEC filings (free, rate-limited)
- **News API** — News sentiment
- **DuckDuckGo** — General web search (free, rate-limited)

---

## 22. Example Workflows

### Example: Full Research Brief for Meridian Health Systems

**Input:**
- Company: Meridian Health Systems (5000-10000 employees, Healthcare, NA)
- Signal hints: Budget range $500K-$5M, Cloud migration interest, Data platform evaluation

**Research Plan:**
1. Signal Discovery: Check funding, earnings, press, leadership changes
2. Hiring Intelligence: Scan Apollo/LinkedIn for tech hiring patterns
3. Executive Intelligence: Track C-suite changes
4. Competitive Intelligence: Map vendor stack from job descriptions
5. Tech Stack Intelligence: Detect technologies from web/jobs
6. Confidence Verification: Validate CDO appointment claim

**Generated Brief (v3):**

```
🏢 Company Overview
Meridian Health Systems is a large integrated healthcare network 
operating across 14 states [1]. With 5,000–10,000 employees and 
a dense footprint of hospitals, outpatient facilities, and telehealth 
platforms, Meridian has invested heavily in clinical data infrastructure [2].

• 14-state hospital network + 60+ outpatient clinics
• Recently completed Epic EHR rollout (FY2025)
• New CDO appointed April 2026 — Dr. Priya Nair, ex-Kaiser
• Publicly listed — MHSYS on NYSE

Sources: [SEC filing: FY2025 Annual Report ↗] [Web: meridianhealth.com ↗]

---

⏱️ Why Now
The CDO appointment creates a narrow high-value window. New C-suite 
hires at Meridian's scale typically complete initial vendor landscape 
reviews within their first 60 days. Dr. Nair's onboarding started 
April 24 — this puts the optimal outreach window at late May to 
mid-June 2026, before she consolidates relationships with existing vendors.

💬 Recommended Angle & Talk Tracks
• Hook: "From what I saw in your CDO's work at Kaiser..."
• Key message: Single data layer for clinical + operational intelligence
• Proof: 3 comparable health system deployments at similar scale
• Avoid: Price-led conversations — Meridian buys on outcome
• Channel: LinkedIn InMail to Dr. Nair + warm intro through James Whitfield
```

### Example Activity Feed

```
10:05  🔍  Scanning SEC filings for budget disclosures (FY2026 10-K)
10:06  🔍  Looking up hiring activity for Meridian Health Systems
10:07  ⚡  Detected executive leadership change: New CDO — Dr. Priya Nair
10:08  🔍  Analyzing job descriptions for technology stack signals
10:09  🔗  Correlating CDO appointment with recent $40M digital health initiative
10:10  ✅  Signal verified against 3 independent sources — confidence: High
10:11  📊  Generating research brief section: Company Overview
10:12  📊  Generating research brief section: Why Now
10:13  📊  Research brief v3 ready — 920 words, 8 sections
10:14  ⚡  Signal heat score updated: 72 → 89 (+17)
```

### Example Signal Correlation

```
Signal A: CDO Appointment (leadership_change, high confidence, Apr 28)
Signal B: 11 Senior IT Hiring (hiring_surge, medium confidence, Apr 2026)
Signal C: $40M Digital Health Initiative (budget_signal, high confidence, Q1 2026)

Correlation Pattern: "Initiative Signal" (leadership + hiring)
  → CDO hire + concentrated platform hiring = active initiative planning
  → Boost factor: 1.5x on both signals

Correlation Pattern: "Budget-Backed Initiative" (budget + hiring)
  → Disclosed budget + aggressive hiring = funded build-out
  → Boost factor: 1.6x on both signals

Combined Signal Heat: 89/100 (composite of 3 signals with correlation boosts)
Recommended Action Window: Late May to mid-June 2026 (60-day CDO evaluation window)
```

### Example Outreach Draft

```
Subject: Meridian Health — a thought on the CDO transition

Hi Priya,

I noticed your appointment as CDO at Meridian — congratulations. 
Your work at Kaiser consolidating disparate data platforms into a 
unified analytics layer is exactly the kind of transformation 
Meridian seems positioned for.

I've worked with three health systems at similar scale going through 
this transition, and there's a pattern: the first 60 days are when 
the most impactful vendor decisions get made.

I have a framework I think would be relevant to your situation at 
Meridian, especially given the $40M digital health initiative and 
the recent platform hiring activity. Happy to share it — no sales 
deck, just context from comparable deployments.

Worth 20 minutes this week?

Best,
[Name]
```

---

## 23. Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| External API rate limits throttle research | High | Medium | Aggressive caching, request queuing, fallback tools |
| LLM hallucinations in outreach | High | Medium | Evidence-only policy, banned phrases, human review gate |
| Signal noise overwhelms users | Medium | High | Confidence filtering, decay, custom rules, muting |
| Brief generation too slow (>2min) | Medium | Medium | Parallel agent execution, streaming sections, skeleton UX |
| External API costs escalate | Medium | Medium | KB-first enrichment, cache TTLs, Haiku for simple tasks |
| Web scraping blocked by targets | Medium | High | Multiple source types, fallback connectors, respect robots.txt |
| Data freshness issues | Medium | Medium | Freshness scores, crawl scheduling, stale warnings |
| Complex multi-agent orchestration fails | High | Low | Graceful degradation, partial results, retry with backoff |
| GDPR compliance for EU contacts | High | Low | EU resident detection, consent tracking, GDPR banners |

---

## 24. Metrics & KPIs

### Product Metrics
- **Signal-to-Action Rate:** % of signals that lead to outreach draft creation
- **Brief Utilization:** % of accounts with viewed briefs
- **Time-to-First-Outreach:** Minutes from signal detection to draft creation
- **Signal Quality Score:** % of signals NOT dismissed within 24 hours
- **Research Completeness:** Average brief sections with sufficient data

### Engineering Metrics
- **Research P95 Latency:** < 90 seconds for full research
- **Brief Generation P95:** < 60 seconds for streaming complete brief
- **Signal Detection P95:** < 5 seconds per company per signal type
- **Cache Hit Rate:** > 60% across all tool calls
- **System Uptime:** 99.5%

### Business Impact Metrics
- **Response Rate Improvement:** Compare signal-anchored vs generic outreach
- **Meeting Book Rate:** Meetings booked per signal acted on
- **Research Time Saved:** Hours saved per week per sales rep
- **Pipeline Velocity:** Time from first signal to qualified opportunity

---

## 25. Future Extensibility

### Near-Term (6 months)
- **Champion Tracking:** Monitor known contacts across companies for job changes
- **Playbooks:** Signal-triggered automation chains (detect → research → brief → outreach)
- **Feedback Loop:** Track outreach outcomes, adjust signal weights via ML
- **Stakeholder Map:** Visual influence mapping for multi-threaded deals

### Medium-Term (12 months)
- **CRM Integration:** Bidirectional sync with Salesforce, HubSpot
- **Email Digest:** Daily/weekly signal summaries via email
- **Team Collaboration:** Shared lists, assignments, territory management
- **Graph Intelligence:** Company relationship graph for referral pathways

### Long-Term (18+ months)
- **Predictive Scoring:** ML model trained on outcome data for intent prediction
- **Conversation Intelligence:** Meeting transcript analysis for signal extraction
- **Market Intelligence:** Industry-level trend detection and benchmarking
- **Custom Agent Builder:** Users define their own specialist research agents

---

## Appendix A: Reuse Matrix

| Existing Component | Reuse Strategy |
|---|---|
| CompanyKnowledgeBase model | Extend with new columns (status, monitoring, tags) |
| Pipeline SSE streaming | Reuse pattern for research progress + brief streaming |
| embedding_service.py | Reuse for semantic search on signals and briefs |
| copilot_agent.py | Add new tools for signal/brief/draft context |
| pipeline_service.py | Reference pattern for research_orchestrator.py |
| export_service.py | Extend for brief PDF export |
| icp_import_service.py | Extend for ingest signal hypothesis configuration |
| All 20+ research tools | Direct reuse by specialist agents |
| PageContextProvider | Extend with new page types for co-pilot |
| Ant Design components | Keep as base, overlay with Quantiv-style custom components |
| TailwindCSS config | Extend with Quantiv accent color palette |
| SSE event handling | Reuse pattern across all streaming endpoints |

## Appendix B: API Endpoint Summary

### New Endpoints

```
# Signals
GET    /api/v1/signals/feed                    # Signal feed with filters
GET    /api/v1/signals/{id}                     # Signal detail
PATCH  /api/v1/signals/{id}/lifecycle           # Save/dismiss/snooze
POST   /api/v1/signals/detect/{company_kb_id}  # Trigger signal detection

# Accounts
GET    /api/v1/accounts                         # Account listing with filters
GET    /api/v1/accounts/{id}                    # Account profile
PATCH  /api/v1/accounts/{id}                    # Update status/tags/config

# Briefs
GET    /api/v1/briefs/{company_kb_id}           # Latest brief
GET    /api/v1/briefs/{company_kb_id}/versions  # All versions
POST   /api/v1/briefs/{company_kb_id}/generate  # Trigger generation (SSE stream)

# Drafts
POST   /api/v1/drafts/generate                  # Generate outreach draft
GET    /api/v1/drafts/{company_kb_id}           # Drafts for account
PATCH  /api/v1/drafts/{id}                      # Update status/content

# Research
POST   /api/v1/research/{company_kb_id}         # Start research job
GET    /api/v1/research/{job_id}/stream          # SSE stream for progress

# Contacts
POST   /api/v1/contacts/{company_kb_id}/enrich  # Trigger enrichment
GET    /api/v1/contacts/{company_kb_id}          # Get contacts

# Custom Signals
GET    /api/v1/custom-signals/rules              # List rules
POST   /api/v1/custom-signals/rules              # Create rule
PUT    /api/v1/custom-signals/rules/{id}         # Update rule
DELETE /api/v1/custom-signals/rules/{id}         # Delete rule

# Custom Sources
GET    /api/v1/sources                           # List sources
POST   /api/v1/sources                           # Add source
PUT    /api/v1/sources/{id}                      # Update source
DELETE /api/v1/sources/{id}                      # Delete source

# Activity
GET    /api/v1/activity/{company_kb_id}          # Company activity feed
GET    /api/v1/activity/research/{job_id}        # Research job activity

# Notifications
GET    /api/v1/notifications                     # List notifications
GET    /api/v1/notifications/unread-count        # Unread count
PATCH  /api/v1/notifications/{id}/read           # Mark read
PATCH  /api/v1/notifications/read-all            # Mark all read

# Monitoring
POST   /api/v1/monitoring/run                    # Trigger monitoring (cron)
```

---

*This document is the authoritative architecture reference for the qlGen Signal Intelligence Platform revamp. All implementation should follow these specifications, adapting details as needed during development while preserving the core architectural decisions and UX philosophy.*
