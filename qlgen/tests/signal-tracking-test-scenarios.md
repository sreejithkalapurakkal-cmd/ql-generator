# Signal Tracking Feature — E2E Test Scenarios

> Target framework: Playwright
> Each scenario is written from an end-user perspective with clear business value.
> Scenarios are grouped by feature area and numbered for traceability.

---

## 1. Signal Feed — Core Viewing

### SF-001: User sees the signal feed page with signals listed
**Precondition:** At least one company in a tracking list has detected signals.
**Steps:** Navigate to `/signals`.
**Expected:** Signal feed page loads. Signals are displayed as cards/rows with title, company name, signal type badge, priority badge, confidence indicator, and detected timestamp.
**Business value:** The signal feed is the primary workspace — if it doesn't render, the entire feature is unusable.

### SF-002: Signal feed displays empty state when no signals exist
**Precondition:** No signals have been detected for any tracked company.
**Steps:** Navigate to `/signals`.
**Expected:** A meaningful empty state is shown (illustration + message like "No signals detected yet") with a CTA to add companies to a tracking list or trigger detection.
**Business value:** New users need guidance on what to do next, not a blank screen.

### SF-003: Signal feed shows correct priority color coding
**Precondition:** Signals exist across all four priority levels (critical, high, medium, low).
**Steps:** Navigate to `/signals`. Observe priority badges.
**Expected:** Each priority level has a distinct, visually differentiable color (e.g., red for critical, orange for high, yellow for medium, gray for low).
**Business value:** Sales reps scan dozens of signals; color coding enables instant triage without reading every label.

### SF-004: Signal card shows all essential information at a glance
**Precondition:** A signal exists with full metadata.
**Steps:** Navigate to `/signals`. Inspect any signal card.
**Expected:** Each card displays: signal title, company name, signal type (e.g., "Funding", "Hiring Surge"), priority badge, confidence score or indicator, relative timestamp (e.g., "2 hours ago"), and source attribution.
**Business value:** Users must be able to triage signals without clicking into each one.

### SF-005: Clicking a signal opens the detail pane
**Precondition:** At least one signal exists in the feed.
**Steps:** Navigate to `/signals`. Click on a signal card.
**Expected:** A detail pane (drawer or expanded section) opens showing: full summary, evidence details, source URLs (clickable), detected date, evidence date, expiry date, and action buttons (dismiss, save, snooze, mark acted-on).
**Business value:** Users need full context to decide whether to act on a signal.

### SF-006: Signal detail pane shows source URL as a clickable link
**Precondition:** A signal exists with a `source_url`.
**Steps:** Open signal detail pane. Click the source link.
**Expected:** The link opens in a new tab pointing to the original source (news article, SEC filing, job posting, etc.).
**Business value:** Users need to verify signal accuracy by checking the original source before taking action.

### SF-007: Signal feed is paginated
**Precondition:** More signals exist than fit on one page (e.g., 50+ signals).
**Steps:** Navigate to `/signals`. Scroll to the bottom or look for pagination controls.
**Expected:** Pagination controls are visible. Clicking "Next" loads the next page. Page number or "showing X of Y" indicator is present.
**Business value:** Performance and usability — loading hundreds of signals at once would be slow and overwhelming.

### SF-008: Signal feed preserves scroll position when returning from another page
**Precondition:** Signal feed has multiple pages of content. User has scrolled down.
**Steps:** Scroll down in the signal feed. Navigate to another page (e.g., Accounts). Press browser Back.
**Expected:** Signal feed returns to the approximate scroll position the user was at.
**Business value:** Users frequently context-switch; losing their place is frustrating and wastes time.

---

## 2. Signal Feed — Tabs & Filtering

### SF-009: "All" tab shows all non-archived, non-dismissed signals
**Precondition:** Signals exist in various states (new, saved, dismissed, archived).
**Steps:** Navigate to `/signals`. Click the "All" tab.
**Expected:** All active signals appear. Dismissed and archived signals do not appear.
**Business value:** Default view should show actionable signals only.

### SF-010: "Today" tab filters signals detected in the last 24 hours
**Precondition:** Signals exist from today and from previous days.
**Steps:** Navigate to `/signals`. Click the "Today" tab.
**Expected:** Only signals detected within the last 24 hours are shown. Older signals are hidden.
**Business value:** Morning routine — sales reps start their day reviewing what's new.

### SF-011: "This Week" tab filters signals from the current week
**Precondition:** Signals exist from this week and older.
**Steps:** Navigate to `/signals`. Click the "This Week" tab.
**Expected:** Only signals from the current calendar week are shown.
**Business value:** Weekly review workflow — managers and reps review the week's intelligence.

### SF-012: "Saved" tab shows only bookmarked signals
**Precondition:** Some signals are saved, others are not.
**Steps:** Navigate to `/signals`. Click the "Saved" tab.
**Expected:** Only signals marked as saved/bookmarked appear.
**Business value:** Users curate important signals they plan to act on later — they need a quick way to find them.

### SF-013: Signal type filter narrows results to selected type
**Precondition:** Signals of multiple types exist (funding, hiring_surge, executive_change, etc.).
**Steps:** Navigate to `/signals`. Select "Funding" from the signal type filter.
**Expected:** Only funding-related signals are displayed. Signal count updates to reflect the filter.
**Business value:** Users working a specific angle (e.g., "companies that just raised money") need to filter by signal type.

### SF-014: Priority filter narrows results to selected priority
**Precondition:** Signals of multiple priorities exist.
**Steps:** Navigate to `/signals`. Select "Critical" from the priority filter.
**Expected:** Only critical-priority signals are shown.
**Business value:** When time is limited, focus on the highest-value signals first.

### SF-015: Multiple filters can be combined
**Precondition:** Diverse signals exist.
**Steps:** Navigate to `/signals`. Select "Funding" type filter AND "High" priority filter.
**Expected:** Only signals matching BOTH criteria are shown.
**Business value:** Precision targeting — "show me high-priority funding signals only."

### SF-016: Clearing filters restores the full signal list
**Precondition:** Filters are applied and showing a subset.
**Steps:** Click a "Clear filters" button or remove individual filter chips.
**Expected:** The full unfiltered signal list reappears.
**Business value:** Users need to easily reset after a focused search.

### SF-017: Tab counts update in real time after signal actions
**Precondition:** Signal feed is open with signals visible.
**Steps:** Save a signal. Switch to the "Saved" tab.
**Expected:** The saved signal appears in the Saved tab. The count on the Saved tab badge increments.
**Business value:** Tabs with stale counts erode trust — users won't believe the system is working.

### SF-018: Filters persist when switching between tabs
**Precondition:** Signals exist with various types.
**Steps:** On the "All" tab, apply a "Funding" type filter. Switch to "This Week" tab.
**Expected:** The "Funding" filter remains applied within the "This Week" context. (Or the filter is cleared with clear UX indication — either behavior is acceptable if consistent.)
**Business value:** Predictable filter behavior reduces cognitive load.

---

## 3. Signal Actions — Dismiss, Save, Snooze, Act-On

### SF-019: Dismissing a signal removes it from the feed
**Precondition:** A signal is visible in the feed.
**Steps:** Click the dismiss/irrelevant button on a signal.
**Expected:** The signal disappears from the feed (with a brief animation/transition). A toast or undo option appears briefly.
**Business value:** Noisy signals clutter the feed — dismissal keeps the workspace clean.

### SF-020: Dismissed signal does not reappear in the feed
**Precondition:** A signal has been dismissed.
**Steps:** Refresh the page. Check all tabs.
**Expected:** The dismissed signal does not appear in any active tab.
**Business value:** Permanent removal of noise — users shouldn't see the same irrelevant signal again.

### SF-021: Saving/bookmarking a signal adds a visual indicator
**Precondition:** An unsaved signal is visible.
**Steps:** Click the save/bookmark button on a signal.
**Expected:** The bookmark icon fills in or changes color. The signal is now marked as saved.
**Business value:** Visual feedback confirms the action was taken.

### SF-022: Saved signal appears in the "Saved" tab
**Precondition:** A signal was just saved.
**Steps:** Switch to the "Saved" tab.
**Expected:** The newly saved signal is listed.
**Business value:** Users curate a shortlist of signals for follow-up.

### SF-023: Unsaving a signal removes it from the "Saved" tab
**Precondition:** A saved signal exists.
**Steps:** Click the unsave/unbookmark button. Switch to the "Saved" tab.
**Expected:** The signal no longer appears in the Saved tab.
**Business value:** Users change their minds — unsaving should be as easy as saving.

### SF-024: Snoozing a signal hides it for the specified duration
**Precondition:** A signal is visible in the feed.
**Steps:** Click the snooze button. Select a duration (e.g., 24 hours).
**Expected:** The signal disappears from the feed. A confirmation message indicates when it will reappear.
**Business value:** "Not now, but later" — the user isn't ready to act but doesn't want to dismiss permanently.

### SF-025: Snoozed signal reappears after the snooze duration expires
**Precondition:** A signal was snoozed with a short duration (for testing, use the smallest available).
**Steps:** Wait for the snooze to expire (or manipulate time in test). Refresh the feed.
**Expected:** The signal reappears in the feed.
**Business value:** Snoozed signals must resurface — otherwise snooze is just a dismiss with extra steps.

### SF-026: Marking a signal as "acted on" changes its visual state
**Precondition:** A signal exists that the user wants to mark as followed-up.
**Steps:** Click "Mark as acted on" on a signal.
**Expected:** The signal's visual state changes (e.g., checkmark icon, "Acted on" badge, muted styling). The acted-on timestamp is visible in the detail pane.
**Business value:** Sales managers need to see which signals have been followed up on vs. ignored.

### SF-027: "Acted on" signals are distinguishable from new signals
**Precondition:** Mix of acted-on and new signals in the feed.
**Steps:** View the signal feed.
**Expected:** Acted-on signals are visually distinct (different styling, badge, or section) from new/unacted signals.
**Business value:** At-a-glance differentiation prevents duplicate outreach and shows progress.

### SF-028: Multiple signals can be acted on in sequence without page reload
**Precondition:** Multiple signals in the feed.
**Steps:** Dismiss signal A. Save signal B. Snooze signal C. Mark signal D as acted on.
**Expected:** Each action completes immediately with visual feedback. No full page reload occurs. Feed updates in place.
**Business value:** Batch triage workflow — reps process 20+ signals in a sitting; page reloads would be unacceptable.

### SF-029: Signal actions are disabled or hidden for archived signals
**Precondition:** An expired/archived signal is visible (e.g., via a specific view or search).
**Steps:** Attempt to interact with an archived signal.
**Expected:** Action buttons are disabled or hidden with a tooltip explaining "This signal has expired."
**Business value:** Prevents confusion — users shouldn't waste time acting on stale intelligence.

---

## 4. Signal Detection — On-Demand

### SD-001: Triggering signal detection for a company starts the process
**Precondition:** A company exists in a tracking list.
**Steps:** Navigate to the company's account profile. Click "Detect Signals" or equivalent CTA.
**Expected:** A loading/progress indicator appears. The system begins detecting signals.
**Business value:** Users need to check for new signals on demand, not just wait for scheduled monitoring.

### SD-002: Signal detection streams progress via SSE
**Precondition:** Signal detection has been triggered.
**Steps:** Observe the progress UI during detection.
**Expected:** Real-time progress updates appear (e.g., "Searching news sources...", "Checking SEC filings...", "Analyzing hiring data..."). Each tool/source is shown as it's being checked.
**Business value:** Long-running operations without feedback feel broken — streaming progress keeps users informed and engaged.

### SD-003: Newly detected signals appear in the feed after detection completes
**Precondition:** Signal detection was triggered and completed.
**Steps:** Navigate to `/signals`.
**Expected:** New signals from the detection run appear in the feed with "just now" timestamps.
**Business value:** The whole point of detection is surfacing new intelligence.

### SD-004: Signal detection for a company with no new signals shows a "no new signals" message
**Precondition:** Signal detection was triggered for a company that has been recently scanned.
**Steps:** Trigger detection. Wait for completion.
**Expected:** A message indicates "No new signals found" rather than failing silently or showing an empty result.
**Business value:** Clarity — the user needs to know the scan completed successfully even with no new findings.

### SD-005: Signal detection can be triggered for an entire tracking list
**Precondition:** A tracking list has multiple companies.
**Steps:** Navigate to the tracking list. Click "Detect Signals" for the entire list.
**Expected:** Detection runs for all companies in the list. Progress shows per-company status.
**Business value:** Batch operation — scanning 50 companies one-by-one would be impractical.

### SD-006: Duplicate signals are not created for the same evidence
**Precondition:** A signal already exists for a specific event (e.g., "Acme Corp raises $50M Series B").
**Steps:** Trigger signal detection again for the same company.
**Expected:** The existing signal is not duplicated. No new signal appears for the same event.
**Business value:** Duplicate signals pollute the feed and erode trust in the system's intelligence.

---

## 5. Signal Types & Content

### ST-001: Funding signals display investment details
**Precondition:** A funding signal has been detected.
**Steps:** Open the signal detail.
**Expected:** The signal shows: funding amount (if available), funding round/stage, investor names (if available), source article link.
**Business value:** Sales reps use funding signals as a trigger — "I noticed you just raised a Series B" in outreach.

### ST-002: Hiring surge signals show role categories and scale
**Precondition:** A hiring surge signal has been detected.
**Steps:** Open the signal detail.
**Expected:** The signal indicates the type of roles being hired (engineering, sales, etc.), approximate number of openings, and growth rate context.
**Business value:** Hiring in specific areas signals budget allocation and strategic priorities.

### ST-003: Executive change signals show the person and role
**Precondition:** An executive change signal has been detected.
**Steps:** Open the signal detail.
**Expected:** The signal shows: person's name, previous role (if known), new role, and the significance of the change.
**Business value:** New CTO = new tech buying cycle. New VP Sales = sales tool evaluation. Executive changes are high-value triggers.

### ST-004: Product launch signals show the product and context
**Precondition:** A product launch signal has been detected.
**Steps:** Open the signal detail.
**Expected:** The signal shows: product/feature name, brief description, launch date, and how it relates to the user's ICP.
**Business value:** Product launches indicate innovation budget and strategic direction.

### ST-005: Press mention signals show the publication and context
**Precondition:** A press mention signal has been detected.
**Steps:** Open the signal detail.
**Expected:** The signal shows: publication name, article headline, publication date, and a summary of why it's relevant.
**Business value:** Press mentions create a conversation opener and indicate company visibility/momentum.

### ST-006: Partnership signals show the partner and deal structure
**Precondition:** A partnership signal has been detected.
**Steps:** Open the signal detail.
**Expected:** The signal shows: partner company name, nature of the partnership, and strategic implications.
**Business value:** Partnerships signal growth, new market entry, and budget reallocation.

### ST-007: Budget signals are surfaced when budget hints are configured
**Precondition:** A tracking list has budget signal hints configured. Detection has run.
**Steps:** Navigate to signal feed. Filter by "Budget Signal" type.
**Expected:** Budget-related signals appear based on the configured hints (e.g., "Q3 procurement cycle", "cloud migration budget approved").
**Business value:** Custom budget hints make signals specific to the user's sales motion.

### ST-008: Urgency signals are surfaced when urgency hints are configured
**Precondition:** A tracking list has urgency signal hints configured. Detection has run.
**Steps:** Filter by "Urgency Signal" type.
**Expected:** Urgency-related signals appear (e.g., "compliance deadline approaching", "contract renewal in 60 days").
**Business value:** Urgency signals identify time-sensitive opportunities that demand immediate outreach.

### ST-009: Custom signals match user-defined rules
**Precondition:** A custom signal rule exists (e.g., keyword-based). Detection has run.
**Steps:** Filter by the custom signal type.
**Expected:** Signals matching the custom rule criteria appear with the configured priority and type.
**Business value:** Every sales team has unique triggers — custom rules make the tool adaptable to any vertical.

---

## 6. Signal Confidence & Heat Score

### SC-001: Confidence score is displayed on each signal
**Precondition:** Signals exist with varying confidence scores.
**Steps:** View the signal feed and signal details.
**Expected:** Each signal shows a confidence indicator (percentage, bar, or tier: high/medium/low). The confidence value is visible without extra clicks.
**Business value:** Users need to gauge reliability — a 95% confidence funding signal is actionable; a 30% one needs verification.

### SC-002: Low-confidence signals are visually de-emphasized
**Precondition:** Signals exist with low confidence scores.
**Steps:** View the signal feed.
**Expected:** Low-confidence signals have a more muted visual treatment compared to high-confidence ones (lighter text, smaller badge, or explicit "low confidence" label).
**Business value:** Prevents users from wasting time on unreliable intelligence.

### SC-003: Heat score is displayed on account/company cards
**Precondition:** Companies have signals with varying heat scores.
**Steps:** Navigate to `/accounts`. View the company list.
**Expected:** Each company card/row shows a heat score or "deal hotness" indicator. Companies with more recent, higher-priority signals have higher heat.
**Business value:** Heat score is the "should I call them today?" indicator — it prioritizes the account list by actionability.

### SC-004: Heat score decays over time for aging signals
**Precondition:** A company had a high heat score from signals detected several days ago. No new signals have been detected since.
**Steps:** Navigate to the accounts list. Check the company's heat score.
**Expected:** The heat score is lower than when the signals were fresh. (In testing, compare before/after a decay cycle.)
**Business value:** Stale intelligence shouldn't rank the same as fresh intelligence — decay ensures the feed reflects current reality.

### SC-005: User can toggle visibility of low-confidence signals in settings
**Precondition:** Low-confidence signals exist.
**Steps:** Navigate to `/settings`. Toggle "Show low-confidence signals" off. Return to the signal feed.
**Expected:** Low-confidence signals are hidden from the feed.
**Business value:** Advanced users want everything; busy reps want only high-confidence signals.

---

## 7. Accounts Page

### AC-001: Accounts page lists all tracked companies
**Precondition:** Multiple companies exist in tracking lists.
**Steps:** Navigate to `/accounts`.
**Expected:** All tracked companies are listed with: company name, domain, industry, signal count, heat score, status, and last activity date.
**Business value:** The accounts page is the master list of all companies being tracked.

### AC-002: Accounts can be sorted by heat score
**Precondition:** Companies have varying heat scores.
**Steps:** Navigate to `/accounts`. Click the heat score column header to sort.
**Expected:** Companies are sorted by heat score descending (hottest first).
**Business value:** "Which account should I work on first?" — sorted by heat answers this instantly.

### AC-003: Accounts can be sorted by signal count
**Precondition:** Companies have varying numbers of signals.
**Steps:** Click the signal count column header.
**Expected:** Companies are sorted by number of active signals.
**Business value:** Signal-rich companies may need attention even if individual signal priority is medium.

### AC-004: Accounts can be sorted by last activity date
**Precondition:** Companies have varying last activity dates.
**Steps:** Click the last activity column header.
**Expected:** Companies are sorted by most recent activity first.
**Business value:** Identifies which accounts have had recent intelligence vs. gone cold.

### AC-005: Accounts can be filtered by status
**Precondition:** Companies exist with different statuses (active, engaged, qualified, etc.).
**Steps:** Select a status filter (e.g., "Active").
**Expected:** Only companies with the selected status are shown.
**Business value:** Sales pipeline management — filter to see only companies in a specific stage.

### AC-006: Accounts can be filtered by tags
**Precondition:** Companies have been tagged.
**Steps:** Select a tag filter.
**Expected:** Only companies with the selected tag are shown.
**Business value:** Tags enable custom grouping (e.g., "conference-leads", "enterprise", "renewal-risk").

### AC-007: Account status can be updated inline
**Precondition:** A company exists on the accounts page.
**Steps:** Click the status field on a company row. Select a new status.
**Expected:** The status updates immediately without page reload. A success indicator appears.
**Business value:** Quick status updates during triage sessions save time.

### AC-008: Account tags can be added and removed
**Precondition:** A company exists on the accounts page.
**Steps:** Click the tags area on a company. Add a new tag. Remove an existing tag.
**Expected:** Tags update immediately. New tags appear as removable chips.
**Business value:** Flexible categorization adapts to any team's workflow.

### AC-009: Account owner can be assigned
**Precondition:** A company exists without an owner.
**Steps:** Click the owner field. Assign an owner.
**Expected:** The owner name appears on the account. The field is editable.
**Business value:** Accountability — knowing who owns an account prevents dropped leads.

### AC-010: Clicking an account navigates to the account profile
**Precondition:** An account exists in the list.
**Steps:** Click on a company name or row.
**Expected:** Navigates to `/accounts/:id` showing the full account profile.
**Business value:** Seamless navigation from list view to detailed profile.

### AC-011: Accounts page shows a signal count badge per company
**Precondition:** Companies have active signals.
**Steps:** View the accounts list.
**Expected:** Each company row shows a badge with the count of active (non-dismissed, non-archived) signals.
**Business value:** At-a-glance signal density helps prioritize which accounts to investigate.

---

## 8. Account Profile Page

### AP-001: Account profile shows company firmographic information
**Precondition:** A company exists with enriched firmographic data.
**Steps:** Navigate to `/accounts/:id`.
**Expected:** The profile shows: company name, domain, industry, sub-industry, location (city, country), employee count, revenue/asset value, description, and tech stack.
**Business value:** Full company context eliminates the need to look up basic info elsewhere.

### AP-002: Account profile shows the company's signal timeline
**Precondition:** A company has signals detected at different times.
**Steps:** Navigate to the account profile. View the signals section.
**Expected:** Signals are displayed in reverse chronological order (newest first) as a timeline. Each entry shows signal type, priority, title, and date.
**Business value:** The timeline tells the "story" of a company — funding round, then hiring surge, then product launch = strong growth narrative for outreach.

### AP-003: Account profile shows best-known contacts
**Precondition:** Contact enrichment has been run for the company.
**Steps:** Navigate to the account profile. View the contacts section.
**Expected:** Key contacts are listed with: name, title, email (if known), LinkedIn URL (if known), and seniority.
**Business value:** Knowing who to contact is half the battle — contacts contextualize signals into actionable outreach.

### AP-004: Triggering signal detection from the account profile
**Precondition:** An account profile is open.
**Steps:** Click "Detect Signals" or "Scan for Signals" button on the profile.
**Expected:** Signal detection starts with streaming progress. New signals appear on the timeline when complete.
**Business value:** On-demand scanning from the account context — the user is already thinking about this company.

### AP-005: Account profile shows the latest research brief
**Precondition:** A brief has been generated for this company.
**Steps:** Navigate to the account profile. View the brief section.
**Expected:** The latest brief is displayed with its sections (Company Overview, Org Structure, Recent Signals, etc.).
**Business value:** The brief is the synthesized intelligence product — the reason users generate briefs is to prepare for calls/meetings.

### AP-006: Account profile shows the activity feed
**Precondition:** Research and signal detection activities have occurred for this company.
**Steps:** View the activity feed section on the profile.
**Expected:** A chronological feed of activities: research events, signal detections, brief generations, contact enrichments, with human-readable narratives.
**Business value:** Activity feed provides audit trail and operational context — "what has the system done for this account?"

### AP-007: Account profile displays monitoring configuration status
**Precondition:** Monitoring has been configured for this company's tracking list.
**Steps:** View the account profile.
**Expected:** Monitoring status is visible: enabled/disabled, frequency, signal types being monitored, alert threshold.
**Business value:** Users need to know if a company is being automatically monitored or if they need to manually scan.

---

## 9. Research Briefs

### RB-001: Generating a research brief for a company
**Precondition:** A company exists with signal data.
**Steps:** Navigate to the account profile. Click "Generate Brief."
**Expected:** Brief generation starts with progress indication. The completed brief shows structured sections: Company Overview, Org Structure, Recent Signals, Competitive Landscape, Tech Stack, Budget Indicators, Why Now, Recommended Angle.
**Business value:** The brief is the key sales enablement output — it prepares reps for calls with synthesized, actionable intelligence.

### RB-002: Brief generation streams progress
**Precondition:** Brief generation has been triggered.
**Steps:** Observe the UI during generation.
**Expected:** Real-time progress updates show which section is being generated. Sections appear incrementally as they complete.
**Business value:** Brief generation takes time (multiple AI calls) — streaming keeps the user engaged instead of staring at a spinner.

### RB-003: Brief shows sources and confidence for each section
**Precondition:** A brief has been generated.
**Steps:** Read through the brief sections.
**Expected:** Each section cites its sources (tool names, URLs) and shows a confidence level for the assertions made.
**Business value:** Reps need to trust the brief content — source attribution enables spot-checking and builds confidence.

### RB-004: Brief versioning — user can access previous versions
**Precondition:** Multiple briefs have been generated for the same company over time.
**Steps:** Navigate to the brief section. Click "Version history" or a version selector.
**Expected:** A list of previous versions appears with dates. Clicking a version shows that historical brief.
**Business value:** Compare how a company's situation has evolved over time — "what changed since last month's brief?"

### RB-005: Brief can be exported as HTML
**Precondition:** A brief exists.
**Steps:** Click "Export" → "HTML."
**Expected:** An HTML file is downloaded that is formatted for print/share with all sections, styling, and source citations intact.
**Business value:** Sales reps share briefs with managers or attach them to CRM records.

### RB-006: Brief can be exported as PDF
**Precondition:** A brief exists.
**Steps:** Click "Export" → "PDF."
**Expected:** A PDF file is downloaded that is clean, professionally formatted, and readable.
**Business value:** PDF is the universal sharing format for stakeholders who don't use the tool.

### RB-007: Brief triggered by a specific signal references that signal
**Precondition:** A user clicks "Generate Brief" from a signal's context (e.g., from the signal detail pane).
**Steps:** Generate a brief triggered by a signal.
**Expected:** The brief's "Why Now" and "Recent Signals" sections prominently feature the trigger signal. The brief is contextualized around that signal event.
**Business value:** Signal-triggered briefs are more actionable — "they just raised $50M, here's what that means for our pitch."

### RB-008: Regenerating a brief creates a new version, not overwriting
**Precondition:** A brief already exists for a company.
**Steps:** Click "Regenerate Brief."
**Expected:** A new version is created. The version number increments. The old version remains accessible.
**Business value:** Data integrity — users should never lose previous intelligence. Append-only versioning is a safety guarantee.

---

## 10. Outreach Drafts

### OD-001: Generating an outreach draft from a company profile
**Precondition:** A company has signal data and/or a brief.
**Steps:** Navigate to the account profile. Click "Generate Outreach Draft" or equivalent.
**Expected:** An outreach message draft is generated incorporating signal intelligence, company context, and the recommended angle from the brief.
**Business value:** The ultimate outcome — turning intelligence into a ready-to-send message.

### OD-002: Outreach draft respects user's voice profile setting
**Precondition:** User has set a voice profile (concise, consultative, or formal) in settings.
**Steps:** Generate an outreach draft.
**Expected:** The draft's tone and length match the configured voice profile.
**Business value:** Every sales rep has their own style — the draft should sound like them, not like a robot.

### OD-003: Outreach draft can be edited before sending
**Precondition:** A draft has been generated.
**Steps:** Edit the draft text directly.
**Expected:** The text is editable. Changes are preserved when saving.
**Business value:** AI-generated drafts are starting points, not final copy — editing is essential.

### OD-004: Outreach draft can be saved as a draft for later
**Precondition:** A draft exists.
**Steps:** Click "Save Draft."
**Expected:** The draft is saved and accessible from the drafts list. Status shows "Draft."
**Business value:** Not every outreach happens immediately — drafts need to be retrievable.

### OD-005: Recent drafts are listed across all companies
**Precondition:** Drafts exist for multiple companies.
**Steps:** Navigate to the recent drafts section (from dashboard or briefs page).
**Expected:** All recent drafts are listed with: company name, draft type (email/LinkedIn), status, creation date.
**Business value:** Centralized draft management prevents "where did I save that draft?"

### OD-006: Draft status can be updated (draft → sent → replied)
**Precondition:** A draft exists.
**Steps:** Change the draft status to "Sent."
**Expected:** The status updates. The signal associated with this outreach is optionally marked as "acted on."
**Business value:** Tracking outreach status closes the loop from signal detection to action.

### OD-007: Outreach format respects settings (email vs. LinkedIn)
**Precondition:** User has set default outreach format to "LinkedIn" in settings.
**Steps:** Generate an outreach draft.
**Expected:** The draft is formatted for LinkedIn messaging (shorter, more conversational) rather than email.
**Business value:** Different channels require different formats — LinkedIn messages that read like emails get ignored.

---

## 11. Custom Signal Rules

### CR-001: Creating a keyword-based custom signal rule
**Precondition:** User navigates to `/signals/rules`.
**Steps:** Click "Create Rule." Select type: "Keyword." Enter keywords (e.g., "cloud migration", "digital transformation"). Set output signal type and priority. Save.
**Expected:** The rule is created and appears in the rules list as "Active." Keywords are displayed.
**Business value:** Users can create signals tailored to their specific sales motion without engineering involvement.

### CR-002: Creating a pattern-based (regex) custom signal rule
**Precondition:** User navigates to `/signals/rules`.
**Steps:** Click "Create Rule." Select type: "Pattern." Enter a regex pattern. Set output signal type and priority. Save.
**Expected:** The rule is created and listed.
**Business value:** Power users can define precise matching patterns for niche signals.

### CR-003: Creating a composite custom signal rule
**Precondition:** User navigates to `/signals/rules`.
**Steps:** Click "Create Rule." Select type: "Composite." Configure conditions (e.g., "Funding AND Hiring Surge within 30 days"). Save.
**Expected:** The rule is created with multi-signal conditions displayed.
**Business value:** Composite rules detect high-value patterns (e.g., "company raised money AND is hiring your buyer persona = hot lead").

### CR-004: Toggling a custom rule on/off
**Precondition:** A custom rule exists and is active.
**Steps:** Click the toggle switch on the rule.
**Expected:** The rule status changes to "Inactive." Toggling back changes it to "Active."
**Business value:** Temporarily disable rules during experimentation without deleting them.

### CR-005: Editing an existing custom rule
**Precondition:** A custom rule exists.
**Steps:** Click "Edit" on the rule. Modify keywords/pattern/conditions. Save.
**Expected:** The rule updates with the new configuration. Changes are reflected immediately.
**Business value:** Rules need tuning — initial keywords may be too broad or too narrow.

### CR-006: Deleting a custom rule
**Precondition:** A custom rule exists.
**Steps:** Click "Delete" on the rule. Confirm the deletion.
**Expected:** The rule is removed from the list. A confirmation dialog prevents accidental deletion.
**Business value:** Cleanup — remove rules that are no longer relevant.

### CR-007: Custom rule shows trigger count and last triggered date
**Precondition:** A custom rule has triggered signals.
**Steps:** View the rules list.
**Expected:** Each rule shows: trigger count (number of times it matched), last triggered date.
**Business value:** Helps users evaluate rule effectiveness — a rule that never triggers may need adjustment.

### CR-008: Test-evaluating rules against a company
**Precondition:** Active rules exist. A company with data exists.
**Steps:** Click "Test Rules" and select a company.
**Expected:** The system evaluates all active rules against the company and shows which rules would match and what signals they would generate, without actually creating signals.
**Business value:** Dry-run testing prevents rule misconfiguration from flooding the feed with false positives.

### CR-009: Custom rule validation prevents invalid configurations
**Precondition:** Creating a new rule.
**Steps:** Try to save a rule with: empty keywords, invalid regex, conflicting composite conditions, or missing required fields.
**Expected:** Validation errors appear with clear messages. The rule is not saved until errors are fixed.
**Business value:** Invalid rules that silently fail or match everything are worse than no rules.

---

## 12. Monitoring Configuration

### MC-001: Enabling automatic monitoring for a tracking list
**Precondition:** A tracking list exists with companies.
**Steps:** Navigate to monitoring settings for the list. Toggle monitoring to "Enabled." Set frequency (e.g., every 3 days). Select signal types to monitor. Set alert threshold. Save.
**Expected:** Monitoring is enabled. Configuration is confirmed with a summary.
**Business value:** Automated monitoring is the "set it and forget it" value proposition — companies are continuously scanned without manual effort.

### MC-002: Adjusting monitoring frequency
**Precondition:** Monitoring is enabled for a tracking list.
**Steps:** Change frequency from 3 days to 7 days. Save.
**Expected:** The new frequency is saved and reflected in the UI.
**Business value:** Different accounts need different cadences — hot prospects daily, cold accounts weekly.

### MC-003: Selecting specific signal types to monitor
**Precondition:** Monitoring configuration is open.
**Steps:** Deselect "press_mention" and "partnership" from the monitored signal types. Save.
**Expected:** Only the remaining signal types are monitored in future runs.
**Business value:** Reduces noise — a user selling HR software doesn't need partnership signals.

### MC-004: Setting alert threshold
**Precondition:** Monitoring configuration is open.
**Steps:** Set alert threshold to "High."
**Expected:** Only signals meeting "High" or "Critical" priority threshold will trigger alerts/notifications.
**Business value:** Prevents alert fatigue — only the most important signals warrant interruption.

### MC-005: Disabling monitoring for a tracking list
**Precondition:** Monitoring is enabled.
**Steps:** Toggle monitoring to "Disabled." Save.
**Expected:** Monitoring stops. No more automatic detection runs occur for this list.
**Business value:** Users need full control — disable monitoring for lists that are on hold or completed.

### MC-006: Dry-run monitoring check shows what would be triggered
**Precondition:** Monitoring is configured.
**Steps:** Click "Preview" or "Dry Run" on the monitoring check.
**Expected:** The system shows which tracking lists are overdue for monitoring and what would be scanned, without actually running detection.
**Business value:** Operational visibility — "what will happen when the next cron fires?"

### MC-007: Monitoring respects the configured frequency
**Precondition:** Monitoring is set to every 7 days. Last run was 3 days ago.
**Steps:** Trigger a monitoring check (manually or via cron).
**Expected:** The tracking list is NOT processed because it's not yet overdue.
**Business value:** Prevents excessive scanning that wastes API credits and creates noise.

---

## 13. Activity Feed

### AF-001: Activity feed shows research events in chronological order
**Precondition:** A company has had research activities.
**Steps:** Navigate to the account profile. View the activity feed section.
**Expected:** Activities are listed newest-first with: timestamp, narrative description, event category icon/badge, and source details.
**Business value:** Audit trail — "what has the system done for this account and when?"

### AF-002: Activity feed supports verbosity levels
**Precondition:** Activity events exist at different verbosity levels.
**Steps:** Toggle between "Summary," "Detailed," and "Technical" verbosity options.
**Expected:** Summary shows high-level milestones only. Detailed shows all activities. Technical shows raw tool outputs and technical details.
**Business value:** Sales reps want summary; data analysts want technical — one feed serves both.

### AF-003: Activity feed shows milestone events prominently
**Precondition:** Milestone events exist (e.g., "Research completed", "Brief generated").
**Steps:** View the activity feed in Summary mode.
**Expected:** Milestones are visually prominent (larger font, different icon, or section divider) compared to regular events.
**Business value:** Milestones are the "what happened" anchors in a potentially long activity stream.

### AF-004: Activity feed can be filtered by category
**Precondition:** Activities exist across categories (research, signal, synthesis, contact, outreach).
**Steps:** Filter by "Signal" category.
**Expected:** Only signal-related activities are shown.
**Business value:** Focused investigation — "show me only signal detection activity for this company."

### AF-005: Activity stats show summary counts
**Precondition:** A company has varied activity.
**Steps:** View the activity stats section.
**Expected:** Stats show: total activities, milestones count, activities by category (research: X, signals: Y, contacts: Z).
**Business value:** Quick health check — "has this account been getting adequate attention?"

### AF-006: Activity feed for a specific research job
**Precondition:** A research job has completed.
**Steps:** Navigate to activity feed and filter by research job, or access via a research job link.
**Expected:** Only activities from that specific research run are shown, in chronological order.
**Business value:** Debugging and review — "what exactly happened during this research run?"

---

## 14. Settings Page

### SE-001: Settings page loads with current user preferences
**Precondition:** User has previously saved settings (or defaults are applied).
**Steps:** Navigate to `/settings`.
**Expected:** All settings sections load with current values: Notifications, Monitoring Defaults, Outreach Defaults, Display Preferences.
**Business value:** Users need to see what's currently configured before making changes.

### SE-002: Toggling notification preferences
**Precondition:** Settings page is open.
**Steps:** Toggle "Signal Detected" notification off. Toggle "Brief Generated" notification on. Save.
**Expected:** Settings are saved. A confirmation message appears.
**Business value:** Notification control prevents alert fatigue while ensuring important events are still surfaced.

### SE-003: Setting default monitoring frequency
**Precondition:** Settings page is open.
**Steps:** Set default monitoring frequency to 5 days. Save.
**Expected:** New tracking lists will default to 5-day monitoring frequency.
**Business value:** Saves time — users don't have to configure monitoring for every list individually.

### SE-004: Configuring default signal types for monitoring
**Precondition:** Settings page is open.
**Steps:** Check/uncheck signal types in the monitoring defaults. Save.
**Expected:** Selected signal types become the default for new monitoring configurations.
**Business value:** Team-wide consistency in what signals are monitored by default.

### SE-005: Setting default alert threshold
**Precondition:** Settings page is open.
**Steps:** Change default alert threshold from "Medium" to "High." Save.
**Expected:** New monitoring configurations will default to "High" threshold.
**Business value:** Prevents over-alerting from the start.

### SE-006: Configuring outreach voice profile
**Precondition:** Settings page is open.
**Steps:** Select "Consultative" voice profile. Save.
**Expected:** Future outreach drafts use a consultative tone.
**Business value:** Personalization — outreach that matches the rep's natural style gets better responses.

### SE-007: Configuring outreach tone
**Precondition:** Settings page is open.
**Steps:** Select "Direct" tone. Save.
**Expected:** Setting is saved. Future outreach drafts use direct language.
**Business value:** Fine-grained control over AI-generated content tone.

### SE-008: Configuring default outreach format
**Precondition:** Settings page is open.
**Steps:** Select "LinkedIn" as default outreach format. Save.
**Expected:** Future outreach drafts default to LinkedIn-optimized formatting.
**Business value:** Teams that primarily use LinkedIn for outreach shouldn't have to switch format every time.

### SE-009: Toggling low-confidence signal visibility
**Precondition:** Settings page is open.
**Steps:** Toggle "Show low-confidence signals in feed" on/off. Save. Navigate to signal feed.
**Expected:** Low-confidence signals appear or disappear based on the setting.
**Business value:** Noise control — experienced users may want all signals; new users benefit from a cleaner feed.

### SE-010: Configuring activity feed verbosity
**Precondition:** Settings page is open.
**Steps:** Change activity feed verbosity from "Summary" to "Detailed." Save. Navigate to an account profile's activity feed.
**Expected:** Activity feed shows detailed narratives instead of summaries.
**Business value:** Persisted preference — users shouldn't have to change verbosity every time they view an activity feed.

### SE-011: Settings persist across sessions
**Precondition:** Settings have been saved.
**Steps:** Log out and log back in (or clear session). Navigate to `/settings`.
**Expected:** All previously saved settings are intact.
**Business value:** Fundamental — settings must be durable, not session-scoped.

---

## 15. Signal Export

### EX-001: Exporting signal report as XLSX from a company
**Precondition:** A company has signals.
**Steps:** Navigate to the company profile or brief. Click "Export Signal Report."
**Expected:** An XLSX file downloads containing: Signal Timeline sheet (all signals with type, priority, date, summary), Correlations sheet (related signals), Summary sheet (aggregate stats).
**Business value:** Offline analysis and sharing with stakeholders who don't have tool access (e.g., leadership presentations).

### EX-002: Exported XLSX contains all active signals
**Precondition:** A company has 10+ signals of various types.
**Steps:** Export signal report. Open the XLSX.
**Expected:** All non-archived signals are present in the report. Each signal has complete data (type, priority, title, summary, source, date, confidence).
**Business value:** Data completeness — a partial export would be misleading.

### EX-003: Exported XLSX has proper formatting and structure
**Precondition:** Signal report is exported.
**Steps:** Open the XLSX in a spreadsheet application.
**Expected:** Columns have headers. Data types are correct (dates as dates, numbers as numbers). Sheets are named clearly. Basic styling is applied (headers are bold, priority cells may be color-coded).
**Business value:** Professional appearance — exports shared with executives need to look polished.

### EX-004: Export works when there are no signals (empty report)
**Precondition:** A company has no signals.
**Steps:** Attempt to export signal report.
**Expected:** Either a meaningful empty report is generated (with headers but no data rows) or the user is shown a message "No signals to export."
**Business value:** Graceful handling — don't download an empty/broken file without explanation.

---

## 16. Dashboard

### DB-001: Dashboard shows signal tracking statistics
**Precondition:** Signal tracking is active with data.
**Steps:** Navigate to `/dashboard`.
**Expected:** Dashboard shows KPIs: total active signals, signals detected today, signals by priority breakdown, signals by type breakdown.
**Business value:** Executive overview — "how is signal tracking performing across all my accounts?"

### DB-002: Dashboard shows recent signals
**Precondition:** Signals have been detected recently.
**Steps:** View the dashboard.
**Expected:** A "Recent Signals" section shows the last 5-10 signals with type, company name, and priority.
**Business value:** Quick pulse check without navigating to the full signal feed.

### DB-003: Dashboard shows recent drafts
**Precondition:** Outreach drafts have been generated.
**Steps:** View the dashboard.
**Expected:** A "Recent Drafts" section shows recent drafts with: company name, status, creation date.
**Business value:** Drafts are action items — surfacing them on the dashboard ensures follow-through.

### DB-004: Dashboard statistics update after new signal detection
**Precondition:** Dashboard is open. Signal detection runs for a company.
**Steps:** Trigger signal detection. Return to dashboard (or observe if auto-refreshing).
**Expected:** Signal counts and recent signals section reflect the newly detected signals.
**Business value:** Stale dashboard data undermines trust in the tool.

### DB-005: Dashboard navigation links work correctly
**Precondition:** Dashboard is open with signal and draft sections.
**Steps:** Click on a signal in the dashboard. Click on a draft in the dashboard.
**Expected:** Signal click navigates to the signal detail (or signal feed with that signal selected). Draft click navigates to the draft editor/viewer.
**Business value:** Dashboard is a launchpad — every item should be one click away from full context.

---

## 17. Contact Enrichment

### CE-001: Enriching contacts for a tracking list
**Precondition:** A tracking list has companies without enriched contacts.
**Steps:** Navigate to the tracking list. Click "Enrich Contacts."
**Expected:** Contact enrichment starts. Progress shows per-company status. Contacts (name, title, email, LinkedIn) are populated for each company.
**Business value:** Signals without contacts are intelligence without action — enrichment completes the picture.

### CE-002: Contact enrichment streams progress
**Precondition:** Enrichment has been triggered.
**Steps:** Observe the enrichment progress UI.
**Expected:** Real-time progress updates: "Enriching Company A... Found 3 contacts", "Enriching Company B... Found 5 contacts."
**Business value:** Enrichment for 50+ companies takes time — progress keeps users informed.

### CE-003: Enriched contacts appear on the account profile
**Precondition:** Contact enrichment has completed for a company.
**Steps:** Navigate to the company's account profile.
**Expected:** The contacts section shows enriched contacts with: name, title, email (if found), LinkedIn URL (if found), and seniority level.
**Business value:** Profile is the single source of truth for an account — contacts must be there.

### CE-004: Enrichment respects target roles configuration
**Precondition:** A tracking list has target roles configured in signal hints (e.g., "VP Engineering", "CTO").
**Steps:** Run contact enrichment.
**Expected:** Discovered contacts prioritize the configured target roles. Results are filtered/ranked by relevance to target roles.
**Business value:** Sales reps need decision-makers, not random employees — target roles focus the enrichment.

### CE-005: Enrichment status is shown per company in the tracking list
**Precondition:** Some companies are enriched, some are not, some are in progress.
**Steps:** View the tracking list.
**Expected:** Each company shows enrichment status: "Not enriched", "In progress", "Enriched (X contacts)."
**Business value:** Operational visibility — which companies still need enrichment?

### CE-006: Re-enriching a company updates existing contacts
**Precondition:** A company already has enriched contacts.
**Steps:** Trigger enrichment again for the same company.
**Expected:** Contacts are updated with latest information. New contacts may be added. Existing contacts are not duplicated.
**Business value:** People change roles — re-enrichment ensures contact data stays current.

---

## 18. Navigation & Layout

### NV-001: Sidebar navigation includes all signal tracking pages
**Precondition:** User is logged in.
**Steps:** View the sidebar navigation.
**Expected:** Sidebar includes links to: Dashboard, Signal Feed, Accounts, Tracking Lists, Settings. Active page is highlighted.
**Business value:** All features must be discoverable and accessible from the main navigation.

### NV-002: Signal feed link in sidebar shows unread signal count badge
**Precondition:** New signals have been detected since the user last viewed the feed.
**Steps:** View the sidebar.
**Expected:** The "Signals" navigation item shows a badge with the count of new/unread signals.
**Business value:** Passive notification — users see there's new intelligence without actively checking.

### NV-003: Browser back/forward navigation works correctly
**Precondition:** User has navigated through multiple pages.
**Steps:** Click browser Back button from account profile. Click browser Forward button.
**Expected:** Navigation history works correctly. Pages load with correct data.
**Business value:** Standard web navigation patterns must work — breaking Back button is a critical UX failure.

### NV-004: Deep linking to a specific signal works
**Precondition:** A signal exists.
**Steps:** Copy the URL of a signal detail page. Open it in a new browser tab.
**Expected:** The signal feed opens with the specific signal selected/expanded.
**Business value:** Users share signal links in Slack/email — deep links must work for collaboration.

### NV-005: Page titles update correctly for each route
**Precondition:** None.
**Steps:** Navigate to each signal tracking page. Check the browser tab title.
**Expected:** Each page has a descriptive tab title (e.g., "Signal Feed | qlGen", "Account: Acme Corp | qlGen").
**Business value:** Users with many tabs need to identify the right one at a glance.

### NV-006: Responsive layout on smaller screens
**Precondition:** None.
**Steps:** Resize the browser window to tablet width (~768px). Navigate through signal feed, accounts, and account profile.
**Expected:** Layout adjusts. Content is readable. Key features remain accessible. No horizontal scrolling on primary content.
**Business value:** Sales reps use laptops with small screens, sometimes in meetings — the tool must be usable.

---

## 19. Error Handling & Edge Cases

### EH-001: Signal detection failure shows a meaningful error
**Precondition:** Signal detection is triggered but an external API fails.
**Steps:** Trigger signal detection (simulate API failure if possible).
**Expected:** An error message is displayed: "Signal detection failed: [specific reason]." The system does not crash. Partial results (from successful tools) are still saved.
**Business value:** Graceful degradation — one failed API shouldn't lose results from five successful ones.

### EH-002: Network disconnection during SSE streaming shows reconnection status
**Precondition:** An SSE stream is active (signal detection, enrichment, or brief generation).
**Steps:** Simulate a brief network disconnection.
**Expected:** The UI shows a "Reconnecting..." indicator. When connection is restored, progress resumes or the final result is shown.
**Business value:** Mobile/laptop users on WiFi experience brief disconnections — the tool should handle this gracefully.

### EH-003: Loading states are shown for all async operations
**Precondition:** None.
**Steps:** Navigate to signal feed, accounts, account profile, and settings. Observe during initial load.
**Expected:** Each page shows a skeleton loader or spinner during data fetch. Content renders when data arrives.
**Business value:** No loading state = user thinks the page is broken or empty.

### EH-004: Empty states are shown for all list views
**Precondition:** A new user with no data.
**Steps:** Visit signal feed, accounts, tracking lists, activity feed, and drafts.
**Expected:** Each page shows a contextual empty state with helpful guidance (not just "No data").
**Business value:** First-run experience — new users need clear guidance on how to get started.

### EH-005: API timeout during brief generation shows a retry option
**Precondition:** Brief generation is attempted.
**Steps:** Simulate a timeout during brief generation.
**Expected:** An error message appears with a "Retry" button. The user can retry without navigating away.
**Business value:** AI operations can timeout due to model latency — retry should be one click, not a full page reload.

### EH-006: Concurrent signal detection for the same company is prevented
**Precondition:** Signal detection is already running for a company.
**Steps:** Attempt to trigger signal detection again for the same company.
**Expected:** The UI prevents double-triggering (button disabled, or message "Detection already in progress").
**Business value:** Prevents wasted API calls and duplicate signals from race conditions.

### EH-007: Very long signal titles/summaries are truncated with "show more"
**Precondition:** A signal exists with a very long title or summary.
**Steps:** View the signal in the feed.
**Expected:** Title/summary is truncated at a reasonable length with a "show more" or expandable control.
**Business value:** Long text breaking the layout makes the feed unusable.

### EH-008: Signal feed handles rapid filter changes gracefully
**Precondition:** Signal feed is loaded with data.
**Steps:** Rapidly click between tabs (All, Today, This Week, Saved) and change filters.
**Expected:** No race conditions. The final selected tab/filter shows correct data. No stale data from a previous request appears.
**Business value:** Real users click fast — race conditions cause confusing data display.

---

## 20. Signal Archival & Expiration

### SA-001: Expired signals are automatically archived
**Precondition:** Signals exist that have passed their expiration date (based on signal type half-life).
**Steps:** Trigger the archive-expired endpoint (or wait for the cron to fire). Check the signal feed.
**Expected:** Expired signals are no longer in the active feed. They may be accessible in an "Archived" view.
**Business value:** Stale signals (e.g., a press mention from 6 months ago) clutter the feed and misdirect outreach.

### SA-002: Different signal types have appropriate expiration periods
**Precondition:** Signals of various types exist.
**Steps:** Check signal expiration dates.
**Expected:** Funding signals have longer half-lives than press mentions. Hiring surges have medium half-lives. Expiration aligns with the signal type's real-world relevance window.
**Business value:** A funding round is relevant for months; a press mention is relevant for days — expiration should match reality.

### SA-003: Archived signals do not contribute to heat score
**Precondition:** A company's heat score includes contributions from now-archived signals.
**Steps:** Archive expired signals. Check the company's heat score.
**Expected:** Heat score decreases because archived signals no longer contribute.
**Business value:** Heat score must reflect current intelligence, not historical.

---

## 21. Signal Correlation

### CO-001: Correlated signals are visually linked
**Precondition:** A company has related signals (e.g., funding round followed by hiring surge within 30 days).
**Steps:** View the company's signal timeline.
**Expected:** Related signals are visually connected (line, grouping, "Related signals" section, or correlation badge).
**Business value:** Correlations tell a story — "they raised money AND started hiring = growth mode" is more powerful than two isolated facts.

### CO-002: Signal correlations appear in the export report
**Precondition:** Correlated signals exist.
**Steps:** Export the signal report for the company.
**Expected:** The XLSX includes a "Correlations" sheet showing which signals are related and the nature of the correlation.
**Business value:** Offline analysis benefits from seeing the full picture, including relationships between signals.

---

## 22. Notifications

### NT-001: Notification is created when a high-priority signal is detected
**Precondition:** Monitoring is enabled with alert threshold "High." A high-priority signal is detected.
**Steps:** Check the notification area after signal detection.
**Expected:** A notification appears: "[Company] — New high-priority signal: [title]."
**Business value:** Proactive alerting for important intelligence — users shouldn't have to poll the signal feed constantly.

### NT-002: Notification is created when a brief is generated
**Precondition:** Brief generation is complete. "Brief Generated" notification is enabled in settings.
**Steps:** Check notifications after brief generation.
**Expected:** A notification appears: "Brief generated for [Company]."
**Business value:** Briefs take time — notification tells the user it's ready without keeping the page open.

### NT-003: Notification is created when contact enrichment completes
**Precondition:** Contact enrichment finishes. "Contact Enriched" notification is enabled.
**Steps:** Check notifications.
**Expected:** A notification appears: "Contact enrichment complete for [Company/List] — X contacts found."
**Business value:** Enrichment runs in background — notification surfaces the result.

### NT-004: Notifications respect user's notification preferences
**Precondition:** User has disabled "Signal Detected" notifications in settings.
**Steps:** Run signal detection. Check notifications.
**Expected:** No signal detection notification is created.
**Business value:** User control over notification volume prevents alert fatigue.

### NT-005: Batch monitoring completion creates summary notification
**Precondition:** Monitoring runs across a tracking list with multiple companies.
**Steps:** Check notifications after monitoring completes.
**Expected:** A single summary notification: "Monitoring complete for [List Name] — X new signals detected across Y companies."
**Business value:** One summary is better than 50 individual notifications — batch notification respects attention.

---

## 23. Data Integrity & Consistency

### DI-001: Signal count on accounts page matches actual signals
**Precondition:** Companies have varying numbers of signals.
**Steps:** Note the signal count badge on an account in the accounts list. Navigate to that account's profile. Count the signals.
**Expected:** The count matches exactly.
**Business value:** Inconsistent counts destroy trust — "it says 5 signals but I can only see 3" = broken experience.

### DI-002: Heat score on accounts page matches the account profile
**Precondition:** A company has a heat score.
**Steps:** Note the heat score on the accounts list. Navigate to the account profile.
**Expected:** The same heat score is displayed in both locations.
**Business value:** Same data, different views — they must agree.

### DI-003: Dismissing a signal from the feed updates the account's signal count
**Precondition:** A company has signals. The accounts page shows the signal count.
**Steps:** Dismiss a signal from the feed for that company. Navigate to accounts page.
**Expected:** The signal count for that company decreases by 1.
**Business value:** Cross-page consistency after actions.

### DI-004: Company data is consistent between tracking list, accounts, and profile
**Precondition:** A company exists in a tracking list with firmographic data.
**Steps:** Check the company name, industry, and status across: tracking list view, accounts page, and account profile.
**Expected:** All three views show identical company information.
**Business value:** Discrepancies suggest data bugs and erode confidence.

### DI-005: Brief version count is consistent
**Precondition:** Multiple brief versions exist for a company.
**Steps:** Check the brief version indicator on the account profile. Open the version history.
**Expected:** The version count matches the number of versions in the history.
**Business value:** Data integrity in the versioning system.

---

## 24. Performance & Responsiveness

### PR-001: Signal feed loads within acceptable time for 100+ signals
**Precondition:** 100+ signals exist in the system.
**Steps:** Navigate to `/signals`. Measure time to first meaningful paint.
**Expected:** The signal feed renders within 3 seconds. Pagination prevents loading all signals at once.
**Business value:** Slow load times = abandoned tool. Performance must scale with real-world data volumes.

### PR-002: Accounts page loads within acceptable time for 500+ companies
**Precondition:** 500+ companies exist in tracking lists.
**Steps:** Navigate to `/accounts`. Measure load time.
**Expected:** The accounts page renders within 3 seconds with pagination or virtual scrolling.
**Business value:** Conference-sourced lists can have 500+ companies — the accounts page must handle this.

### PR-003: Signal actions (save, dismiss, snooze) respond within 1 second
**Precondition:** Signal feed is loaded.
**Steps:** Perform save, dismiss, and snooze actions. Measure response time.
**Expected:** Each action completes (visual feedback) within 1 second.
**Business value:** Triage is rapid-fire — laggy actions break the flow.

### PR-004: SSE streaming maintains connection for long-running operations
**Precondition:** Signal detection or enrichment is triggered for a large list.
**Steps:** Observe the SSE stream for the full duration of a 5+ minute operation.
**Expected:** The connection is maintained. No dropped events. Progress updates continue until completion.
**Business value:** Dropped connections during long operations create confusion about whether the operation succeeded.

### PR-005: Filter changes update results without full page reload
**Precondition:** Signal feed or accounts page is loaded.
**Steps:** Apply and remove filters.
**Expected:** Results update in-place. No full page reload. URL query parameters may update for shareability.
**Business value:** Smooth filtering is essential for fast exploration.

---

## 25. Accessibility & Usability

### AX-001: All interactive elements are keyboard navigable
**Precondition:** None.
**Steps:** Navigate the signal feed, accounts page, and settings using only keyboard (Tab, Enter, Escape, Arrow keys).
**Expected:** All buttons, links, filters, tabs, and form controls are reachable and operable via keyboard.
**Business value:** Accessibility compliance and power-user efficiency.

### AX-002: Signal priority badges have accessible labels
**Precondition:** Signals with different priorities exist.
**Steps:** Inspect priority badges with a screen reader or check ARIA attributes.
**Expected:** Each badge has an accessible label (e.g., aria-label="Critical priority") beyond just color.
**Business value:** Color-blind users cannot distinguish priority by color alone.

### AX-003: Modal/drawer close with Escape key
**Precondition:** A signal detail pane or modal is open.
**Steps:** Press Escape.
**Expected:** The modal/drawer closes.
**Business value:** Standard UX pattern — users expect Escape to close overlays.

### AX-004: Form inputs have visible labels and error messages
**Precondition:** Settings page or custom rule creation form is open.
**Steps:** Inspect form fields. Submit an invalid form.
**Expected:** All inputs have visible labels. Error messages appear near the relevant field with clear descriptions.
**Business value:** Forms without labels are inaccessible and confusing.

### AX-005: Toast/confirmation messages are perceivable
**Precondition:** None.
**Steps:** Perform actions that trigger toast messages (save signal, dismiss signal, save settings).
**Expected:** Toast messages appear in a consistent location, persist long enough to read (3-5 seconds), and are announced to screen readers.
**Business value:** If the user can't see the confirmation, they don't know if their action worked.

---

## 26. Cross-Feature Workflows (End-to-End Journeys)

### E2E-001: Full signal-to-outreach workflow
**Precondition:** A company is in a tracking list.
**Steps:**
1. Trigger signal detection for the company.
2. View the detected signal in the feed.
3. Open signal detail, verify evidence.
4. Generate a research brief from the signal context.
5. Generate an outreach draft from the brief.
6. Edit and save the draft.
7. Mark the signal as "acted on."
**Expected:** Each step completes successfully. The brief references the signal. The outreach draft incorporates brief insights. The signal is marked as acted on. Activity feed shows the full journey.
**Business value:** This is THE core workflow — signal detection → intelligence synthesis → action. If this breaks, the product fails.

### E2E-002: Morning triage workflow
**Precondition:** Overnight monitoring has detected new signals.
**Steps:**
1. Navigate to dashboard, check signal stats.
2. Navigate to signal feed, click "Today" tab.
3. Review each new signal: save the important ones, dismiss the irrelevant ones, snooze ones needing follow-up.
4. For saved signals, navigate to account profiles and review context.
5. Generate outreach drafts for the highest-priority signals.
**Expected:** All steps flow smoothly with no navigation friction. Tabs and filters work as expected. Actions update the feed correctly.
**Business value:** This is the daily routine for sales reps — the tool must support this workflow seamlessly.

### E2E-003: Conference follow-up workflow
**Precondition:** A tracking list has been created with 50+ companies from a conference.
**Steps:**
1. View the tracking list with all companies.
2. Run contact enrichment for the list.
3. Run signal detection for the list.
4. Navigate to accounts page, sort by heat score.
5. Open the top-3 hottest accounts, review their signals and contacts.
6. Generate briefs and outreach drafts for the top accounts.
**Expected:** All operations work at scale (50+ companies). Enrichment and detection handle the batch. Accounts sort correctly by heat. Briefs and drafts are relevant.
**Business value:** This is the origin story for the feature — the user who returned from a conference with 500+ companies. The full workflow must work end-to-end.

### E2E-004: Custom rule creation and validation workflow
**Precondition:** None.
**Steps:**
1. Create a custom keyword rule (e.g., "cloud migration").
2. Test the rule against an existing company (dry run).
3. Verify the test shows what signals would be generated.
4. Run signal detection for that company.
5. Verify the custom rule generates signals in the feed.
6. Check the rule's trigger count has incremented.
**Expected:** The rule is created, tested, triggers correctly, and statistics are tracked.
**Business value:** Custom rules are a differentiator — this workflow validates the entire custom rule lifecycle.

### E2E-005: Account lifecycle management workflow
**Precondition:** A new company has been added to a tracking list.
**Steps:**
1. View the company on the accounts page (status: new/active).
2. Run signal detection — signals appear.
3. Update status to "Engaged" after reviewing signals.
4. Add tags ("enterprise", "Q3-target").
5. Assign an owner.
6. Generate a brief.
7. Generate an outreach draft. Mark as sent.
8. Mark signal as "acted on."
9. Update status to "Qualified" after positive response.
**Expected:** All status transitions work. Tags and owner persist. The account's progression is reflected in the activity feed.
**Business value:** Account lifecycle management from discovery to qualification — the complete sales development workflow.

### E2E-006: Settings configuration affects downstream behavior
**Precondition:** Default settings are active.
**Steps:**
1. Set voice profile to "Formal" and format to "LinkedIn" in settings.
2. Set monitoring defaults: frequency 7 days, threshold "Critical."
3. Disable "Show low-confidence signals."
4. Navigate to signal feed — verify low-confidence signals are hidden.
5. Generate an outreach draft — verify it uses formal tone and LinkedIn format.
6. Enable monitoring for a new list — verify it defaults to 7 days and "Critical."
**Expected:** Settings propagate to all downstream features correctly.
**Business value:** Settings that don't actually affect behavior are worse than useless — they're misleading.

---

## Summary

| Category | Count |
|---|---|
| Signal Feed — Core Viewing | 8 |
| Signal Feed — Tabs & Filtering | 10 |
| Signal Actions | 11 |
| Signal Detection | 6 |
| Signal Types & Content | 9 |
| Signal Confidence & Heat Score | 5 |
| Accounts Page | 11 |
| Account Profile Page | 7 |
| Research Briefs | 8 |
| Outreach Drafts | 7 |
| Custom Signal Rules | 9 |
| Monitoring Configuration | 7 |
| Activity Feed | 6 |
| Settings Page | 11 |
| Signal Export | 4 |
| Dashboard | 5 |
| Contact Enrichment | 6 |
| Navigation & Layout | 6 |
| Error Handling & Edge Cases | 8 |
| Signal Archival & Expiration | 3 |
| Signal Correlation | 2 |
| Notifications | 5 |
| Data Integrity & Consistency | 5 |
| Performance & Responsiveness | 5 |
| Accessibility & Usability | 5 |
| Cross-Feature Workflows (E2E) | 6 |
| **Total** | **180** |
