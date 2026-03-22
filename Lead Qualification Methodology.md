# **Lead Qualification Methodology**

---

## **1\. ICP Definition & Signal Mapping**

### **Beyond Basic Firmographics**

Most teams stop at industry \+ headcount \+ revenue. That's table stakes. A real ICP has four layers:

**Firmographic Layer (Company Profile)**

* Industry vertical (NAICS/SIC codes — be specific; "technology" is useless, "cloud-native SaaS companies serving financial services" is actionable)  
* Employee count *by department*, not just total headcount (a 500-person company with 3 engineers vs. 200 engineers are completely different buyers)  
* Revenue range AND revenue growth rate (a $10M company growing 300% YoY beats a stagnant $50M company every time)  
* Funding stage and total capital raised (seed vs. Series B vs. PE-backed have radically different buying motions, budget cycles, and decision-making authority)  
* Geographic presence (HQ vs. distributed vs. international — matters for compliance, procurement, and champion access)  
* Business model (B2B vs. B2C vs. marketplace — determines who feels the pain your product solves)

**Technographic Layer (What They're Running)**

* Current tech stack via tools like BuiltWith, HG Insights, Slintel, or Bombora  
* Specific integrations they've deployed (e.g., if you sell a data pipeline tool, a company running Snowflake \+ Fivetran \+ dbt is a warm fit; one on legacy Oracle is a longer sell)  
* Tech *recency* signals — are they adopting new tools or running 10-year-old infrastructure? (Modernizers buy; laggards stall)  
* ⭐ Presence of *adjacent* or *complementary* tools (if they're using Salesforce \+ Outreach \+ ZoomInfo, they have a functioning revenue stack and are likely to add to it)  
* Absence of a *competing* tool in your category (confirms greenfield opportunity vs. rip-and-replace, which has 2-3x longer sales cycles)

**Psychographic Layer (How They Think)**

* Company values as expressed in public content: job postings, CEO LinkedIn posts, press releases, investor decks  
* Risk tolerance: are they early adopters (cite new tools, blog about experimentation) or fast followers?  
* Operational philosophy: PLG companies think differently about software adoption than top-down enterprise buyers  
* ⭐ Leadership orientation: a CRO who posts about pipeline efficiency is pre-sold on your sales intelligence tool before you call them. Mine LinkedIn for thought leadership signals — they tell you the *language* and *framing* to use in outreach

**Behavioral Layer (What They're Doing Right Now)**

* Website visit patterns (via intent platforms like Bombora, G2 Buyer Intent, TechTarget Priority Engine)  
* Content consumption: downloading competitor whitepapers, attending webinars in your category  
* Job posting patterns (see Section 2\)  
* Review activity on G2, Capterra, TrustRadius (reviewing competitors \= actively evaluating)

### **Signal Weighting Framework**

Weight signals across two axes: **fit** (are they the right type of buyer?) and **intent** (are they ready to buy now?).

| Signal Type | Fit Weight | Intent Weight | Notes |
| ----- | ----- | ----- | ----- |
| Firmographic | High | Low | Establishes baseline eligibility |
| Technographic | High | Medium | Stack fit \= fit; stack *change* \= intent |
| Psychographic | Medium | Medium | Hard to automate; highest ACV impact |
| Behavioral/Intent | Low | Very High | The highest-leverage intent signal available |

Apply a weighted composite score, not a simple sum. A company that scores 90% on fit but 10% on intent should rank *below* a 70% fit / 80% intent company in most short-cycle sales motions. For enterprise (12+ month cycles), fit weight increases because you're planting seeds.

**Segment-specific weighting:**

* **SMB:** Overweight intent (budget cycles are short, decisions are fast, timing dominates)  
* **Mid-market:** Balance fit and intent roughly equally  
* **Enterprise:** Overweight fit — buying committees, long cycles, and political complexity mean you need strong structural fit to justify the investment

**AI Instruction Summary:** Define ICP as a four-layer profile (firmographic, technographic, psychographic, behavioral); score each signal independently on a fit axis and an intent axis; apply segment-specific composite weighting where SMB overweights intent and enterprise overweights fit.

---

## **2\. Source Strategy**

### **Sources, Signals, and What They Actually Tell You**

**LinkedIn (Fit \+ Intent)**

* *What to extract:* Headcount by department (Sales Navigator filters), hiring velocity, job title structures (a "VP of Revenue Operations" signals process maturity), leadership tenure, recent posts by economic buyers  
* *Fit signal:* Org structure, seniority density in target department  
* ⭐ *Intent signal:* A VP of Sales who just posted "we're scaling our outbound motion" is telling you their budget priority. Set up Boolean alerts for keywords like "evaluating," "scaling," "implementing," "struggling with" in your ICP titles' posts  
* *Limitation:* Data goes stale fast at the individual level; company-level signals are more reliable

**Apollo.io / ZoomInfo / Lusha (Fit \+ Contact Data)**

* *What to extract:* Direct dials, verified emails, org charts, technographics, intent scores (ZoomInfo's Intent is Bombora-powered)  
* *Fit signal:* Firmographics, tech stack, department sizing  
* *Intent signal:* ZoomInfo Scoops (leadership changes, funding, initiatives), Apollo's intent topics  
* *Note:* Data quality varies significantly by segment. Enterprise contact data is more reliable than SMB. Always validate emails before sequencing.

**Bombora / G2 Buyer Intent / TechTarget Priority Engine (Intent — Highest Signal)**

* ⭐ *What to extract:* Topic-level intent surges (companies consuming above-baseline content about your category's keywords over a 2-4 week window)  
* *Why it matters:* A company spiking on topics like "sales intelligence software" and "lead enrichment tools" is in an active buying cycle *right now* — this is the closest thing to a hand-raise you get before the RFP  
* *G2 specifically:* Competitors' profile visitors \= people actively comparing solutions. This is the highest-conversion intent data available in B2B  
* *Limitation:* Intent data has noise; a single spike means less than a sustained 3-week surge across multiple related topics

**Crunchbase / PitchBook (Fit \+ Timing)**

* *What to extract:* Funding rounds (amount, stage, lead investors, date), M\&A activity, leadership changes, headcount growth curves  
* *Intent signal:* ⭐ Funding events — specifically Series A/B/C rounds within the last 90 days — are among the highest-converting timing triggers in B2B sales. Companies that just raised have: new budget, board pressure to show growth, and a mandate to build infrastructure. The window is roughly 30-120 days post-announcement before the org is "locked in" on vendors  
* *M\&A signal:* Acquirer often needs to consolidate tech stacks \= displacement opportunity. Target often gets budget frozen \= avoid until integration settles (usually 6-12 months)

**Job Boards (LinkedIn Jobs, Indeed, Greenhouse, Lever, Workday) — Highly Underrated**

* ⭐ *What to extract:* Role titles being hired, volume of postings in target departments, specific tools mentioned in job descriptions, seniority level of open roles  
* *Fit signal:* "We're hiring 10 SDRs" \= they have an outbound motion (relevant if you sell sales tools)  
* *Intent signal:* Hiring a "Director of Sales Operations" \= they're building process infrastructure \= timing opportunity for RevOps/sales stack tools. Hiring a "Data Engineer" to work with Snowflake \= cloud data initiative underway \= timing for data tools  
* Job descriptions often reveal *exactly* which tools they're currently using and which they plan to adopt — it's accidental competitive intelligence

**G2 / Capterra / TrustRadius (Intent — Active Evaluators)**

* *What to extract:* Recent reviews of competitors, rating trends, "what we wish it had" comments in reviews  
* *Intent signal:* A company leaving a 3-star review of your competitor citing a specific weakness *your product solves*\= the highest-quality warm lead you can generate without inbound

**Company Website / Press Releases / News (Fit \+ Timing)**

* *What to extract:* Product announcements, new market entries, leadership quotes, partnership announcements, "we're hiring" blog posts  
* *Timing signal:* "We're expanding into EMEA" \= they need localized tools, compliance infrastructure, new vendor relationships  
* Use tools like Google Alerts, Mention.com, or Feedly to monitor target accounts for trigger events

**Reddit / Slack Communities / Discord (Psychographic \+ Intent)**

* Often overlooked but extremely high signal. Communities like r/sales, r/devops, RevGenius Slack, Pavilion have practitioners asking "has anyone used X tool?" or "we're evaluating Y vs. Z" — these are real buying conversations happening in public  
* Hard to scale but worth monitoring for named account lists in enterprise

**AI Instruction Summary:** For each lead, query firmographic/contact sources (Apollo, ZoomInfo) for fit signals, intent platforms (Bombora, G2) for buying activity, Crunchbase for timing triggers, and job board data for initiative signals; weight intent data sources highest for near-term pipeline and firmographic sources highest for long-term account development.

---

## **3\. Qualification Framework**

### **BANT Applied Precisely (Not as It's Typically Misused)**

BANT was designed by IBM in the 1950s for transactional sales. In modern B2B it's a *disqualification* framework, not a qualification checklist. Here's how to apply it without destroying pipeline:

**Budget**

* In SMB: Can be confirmed early — ask directly, or infer from pricing page behavior (did they visit the enterprise tier?)  
* In mid-market/enterprise: Budget exists as an *allocation problem*, not a binary yes/no. The question is: "Is there a budget category this maps to, and is it owned by someone we can reach?"  
* *Proxy signals when direct confirmation isn't possible:* Company size \+ peer benchmarks (e.g., companies of this size in this industry typically spend $X-Y on this category); recent funding (post-Series B companies typically have $50-200K available for sales/marketing stack tools); tech stack density (companies running 15+ MarTech tools clearly have discretionary software budget)  
* ⭐ *Red flag:* "We have budget but it's frozen until Q3" with no specific unfreezing trigger \= not a real near-term opportunity. Route to nurture.

**Authority**

* Map the buying committee, not just a single champion. In enterprise, there are typically: Economic Buyer (signs the PO), Champion (internal advocate), Users (practitioners), and Blocker (IT/Legal/Procurement)  
* *Signal for authority:* Title \+ reporting structure. A "Director of Sales" who reports to a CRO at a 500-person company has budget authority up to \~$50K. Above that, CRO signature required. Knowing this prevents wasting 6 weeks selling to someone who can't approve  
* *LinkedIn org chart mining:* Identify who the champion reports to and map the chain to the economic buyer before the first call  
* *Red flag:* Your champion has been in their role less than 6 months. They don't have political capital yet. Not disqualifying, but lengthens the cycle — factor into timing score.

**Need**

* *Explicit need:* They've told you (inbound, event conversation, response to outreach)  
* *Implicit need:* Inferred from signals — hiring patterns, tech stack gaps, intent data, peer benchmarking  
* ⭐ The distinction between *pain* and *need* matters enormously. Pain is "our SDRs are spending 4 hours/day on manual research." Need is "we need a lead intelligence tool." AI systems should be prompted to identify *pain indicators* (complaints, inefficiency signals, scale friction) not just surface-level need statements  
* Segment note — **Enterprise:** Need is almost always political. The VP who *owns* the pain may not be the one who *sponsors* the solution. Map both.

**Timeline**

* "Likely buyer now" indicators: Funding event in last 90 days \+ budget owner identified \+ tech stack gap confirmed \+ intent surge active \= compress timeline, prioritize  
* "Good fit, wrong timing" indicators: Strong ICP fit, no intent signals, no trigger events, champion new to role \= put in 90-day nurture with trigger-based re-engagement  
* ⭐ *The most reliable timing signal:* Fiscal year end/start. Companies with Dec 31 fiscal years start evaluating new tools in September-October for next-year budget. Companies with Jan 31 fiscal years are in budget season November-December. Knowing a prospect's fiscal calendar is worth more than any intent data platform.

### **Disqualification Red Flags**

Apply these as hard filters before any scoring:

1. **Competitor customer with active contract** (unless you have specific displacement intel)  
2. **Recent failed implementation** of a tool in your category — they're burned, sales cycle will be 2-3x normal  
3. **Acquisition in progress** — budget frozen, org in flux, no one owns decisions  
4. **Champion departure** — your deal dies with them unless you can re-map within 2 weeks  
5. **IT-led evaluation with no business sponsor** — IT will optimize for security/compliance, not ROI; deals stall or die  
6. **Company declining in headcount** per LinkedIn signals — shrinking companies don't buy growth tools

**AI Instruction Summary:** Apply BANT as a disqualification lens, not a checklist; score Budget as a probability estimate using proxy signals when direct data is unavailable; flag champion authority risk based on tenure and reporting structure; use fiscal year timing data to calibrate urgency; hard-filter leads matching any of the six disqualification red flags.

---

## **4\. Scoring & Ranking Logic**

### **Four-Dimension Scoring Model**

Score every lead on four independent dimensions, then combine using segment-weighted aggregation:

**Dimension 1: Fit Score (0-100)** Measures structural alignment with ICP.

| Sub-signal | Weight |
| ----- | ----- |
| Industry vertical match | 25% |
| Headcount (dept-level) | 20% |
| Revenue/growth rate | 20% |
| Tech stack alignment | 20% |
| Business model match | 15% |

Fit score changes slowly. Recalculate quarterly or on major company event (funding, M\&A).

**Dimension 2: Intent Score (0-100)** Measures evidence of active buying behavior.

| Sub-signal | Weight |
| ----- | ----- |
| Bombora/G2 intent surge (topic relevance \+ recency) | 35% |
| G2 competitor review activity | 25% |
| Website behavior (if available via reverse IP or pixel) | 20% |
| LinkedIn engagement with your content/category | 20% |

⭐ Intent score is highly time-decayed. A surge 60 days ago is worth \~30% of a surge today. Build in exponential decay: `intent_score = raw_score × e^(-λ × days_since_signal)` where λ ≈ 0.02-0.03 for most B2B categories (intent half-life ≈ 30-45 days).

**Dimension 3: Timing Score (0-100)** Measures environmental readiness to buy.

| Sub-signal | Weight |
| ----- | ----- |
| Funding event recency (0-90 days \= 100, 91-180 \= 60, 181+ \= 20\) | 30% |
| Fiscal year alignment (budget season \= high, mid-year \= low) | 25% |
| Leadership change recency (new VP in relevant role \= high) | 25% |
| Hiring surge in relevant department | 20% |

**Dimension 4: Reachability Score (0-100)** Measures probability of making contact with the right person.

| Sub-signal | Weight |
| ----- | ----- |
| Verified direct contact data (email \+ phone) available | 40% |
| Champion identified and mapped | 30% |
| LinkedIn connection depth (1st/2nd degree to buyer) | 20% |
| Company size (inversely correlated — smaller \= more reachable) | 10% |

### **Composite Scoring by Segment**

* **SMB:** `(Fit × 0.20) + (Intent × 0.40) + (Timing × 0.25) + (Reachability × 0.15)`  
* **Mid-Market:** `(Fit × 0.30) + (Intent × 0.30) + (Timing × 0.25) + (Reachability × 0.15)`  
* **Enterprise:** `(Fit × 0.40) + (Intent × 0.25) + (Timing × 0.20) + (Reachability × 0.15)`

### **Handling Incomplete Data**

⭐ This is where most scoring systems fail — they either zero out missing signals (which penalizes companies unfairly) or ignore missing data (which inflates scores). The correct approach:

* **Known absence:** You searched for intent data and found none → score \= 20 (low but not zero; absence of signal ≠ absence of intent)  
* **Data unavailable:** Source didn't return data → impute using *segment peer median* for that signal (e.g., if revenue data missing, use median revenue for companies of that headcount in that industry)  
* **Conflicting signals:** Two sources contradict each other → use the more *recent* data source; flag the conflict as a data quality note in the output  
* Apply a **confidence multiplier** (0.6-1.0) to the composite score based on data completeness. A lead with 90% data completeness scoring 75 composite beats a lead with 50% completeness scoring 80 composite. Surface this to the rep.

**AI Instruction Summary:** Score leads on four independent dimensions (Fit, Intent, Timing, Reachability); apply segment-specific weighting to the composite; decay intent scores exponentially with time; impute missing data using segment peer medians rather than zeroing; attach a data confidence multiplier to every composite score.

---

## **5\. Personalization Hooks**

### **The Research Stack for Outreach Personalization**

Personalization at scale requires a tiered approach. Not every lead gets the same depth of research:

* **Tier 1 (Top 10 accounts):** Deep manual research — 30-45 minutes per account. Read their last 3 earnings calls or investor updates, every LinkedIn post from the economic buyer in the last 90 days, recent press releases, G2 reviews they've written, job descriptions in their open roles  
* **Tier 2 (Accounts 11-50):** Structured signal research — 10-15 minutes. Trigger events \+ tech stack \+ one buyer-specific insight  
* **Tier 3 (Accounts 51-100):** AI-assisted synthesis — trigger event \+ ICP match reason \+ one personalized opening line generated from public data

### **Trigger Events (Ranked by Conversion Impact)**

⭐ **Tier A Triggers (Highest urgency — outreach within 48 hours):**

1. **New VP/Director hired in your buyer persona role** — New leaders have 90-day mandates, are benchmarking vendors, and haven't committed to incumbents yet. This is the single highest-converting trigger in B2B sales. Source: LinkedIn, ZoomInfo Scoops, press releases  
2. **Funding announcement (Series A, B, C)** — New capital, new mandates, new headcount, new tool budget. Source: Crunchbase, TechCrunch, PitchBook  
3. **G2 competitor review posted (3 stars or below)** — Active dissatisfaction with incumbent. Source: G2 Buyer Intent

**Tier B Triggers (High urgency — outreach within 1 week):** 4\. **Significant hiring surge in target department** (3+ relevant roles posted in 30 days) — Scaling pain \= buying trigger. Source: LinkedIn Jobs 5\. **New product launch or market expansion announcement** — Infrastructure needs change. Source: Press releases, company blog 6\. **Tech stack change detected** — Migrating off a platform \= re-evaluating the whole stack. Source: BuiltWith delta reports, HG Insights

**Tier C Triggers (Moderate urgency — outreach within 2 weeks):** 7\. **Leadership content engagement** — Liked/commented on content in your category 8\. **Conference speaking or attendance signals** (Dreamforce, SaaStr, etc.) 9\. **Competitor contract renewal window** — If you know typical contract lengths (ZoomInfo is typically 1-year, Salesforce is often 3-year), time your outreach 90 days before estimated renewal

### **What to Look For in Buyer Research**

* **Their stated priorities:** Recent all-hands themes (Glassdoor reviews sometimes reveal these), LinkedIn posts, conference talks  
* **Their professional background:** If the new VP of Sales came from a company that used your tool, they're pre-sold. If they came from a competitor's customer, understand their biases  
* **Their company's competitive position:** Are they gaining or losing market share? (press coverage, G2 category movement, hiring velocity vs. competitors)  
* ⭐ **The language they use:** Mirror their exact vocabulary in outreach. If they say "revenue efficiency" don't say "sales productivity." If they say "go-to-market" don't say "sales and marketing." Language matching in subject lines and opening lines measurably lifts response rates

**AI Instruction Summary:** Classify each lead by research tier based on composite score; identify the highest-tier trigger event available for each lead; extract the economic buyer's stated language and priorities from LinkedIn and public content; generate personalization hooks that reference specific trigger events and mirror the buyer's own vocabulary.

---

## **6\. Output & Prioritization**

### **What AEs and SDRs Actually Need (Not What BI Teams Think They Need)**

The output of a lead qualification system isn't a spreadsheet. It's a *work order*. Every lead should come with enough context that a rep can make the first call within 20 minutes of seeing the record — no additional research required.

### **Required Metadata Per Lead**

**Identity Layer**

* Company name, website, HQ location, employee count (total \+ target department)  
* Primary contact: Name, title, verified email, direct dial, LinkedIn URL  
* Secondary contacts: Economic buyer and potential blocker (name \+ title only if full data not available)

**Qualification Layer**

* Composite score (0-100) with breakdown by dimension (Fit: X, Intent: X, Timing: X, Reachability: X)  
* Data confidence score (% of signals confirmed vs. imputed)  
* ICP match summary: 2-3 sentences on *why* this company fits (not just that it does)  
* Qualification stage: "Ready Now" / "30-60 Day Nurture" / "90+ Day Nurture"

**Intelligence Layer**

* ⭐ Top trigger event: The single most relevant, timely reason to reach out *right now* (with date and source)  
* Tech stack: Current tools in relevant categories (what they have, what's missing, what might be replaced)  
* Recent company news: 1-3 bullet points (funding, hires, product launches, partnerships) from last 90 days  
* Competitor relationship: Known incumbent in your category (if detectable) \+ estimated contract stage

**Personalization Layer**

* ⭐ Suggested opening line: 1-2 sentences referencing the trigger event in the buyer's language  
* Relevant pain signals: Specific evidence of the problem your product solves (job description language, review complaints, LinkedIn posts)  
* Mutual connections or shared context: 1st/2nd degree LinkedIn connections to the buyer

**Operational Layer**

* Recommended outreach sequence: Email first / LinkedIn first / Call first (based on seniority \+ company size)  
* Suggested cadence timing: Day of week and time of day optimized for persona (e.g., VP Sales \= Tuesday-Thursday 8-9am or 5-6pm; Developers \= async is better, use email)  
* CRM hygiene: Flag if account already exists in CRM, if there's an open opportunity, or if there's a previous contact history

### **Prioritization Display Logic**

Present leads in three tiers, not a flat ranked list:

**🔴 Act Now (Score 75-100, Timing Score 70+):** Reach out today. Include trigger event with urgency note.

**🟡 Pipeline This Week (Score 55-74, or high Fit with moderate Intent):** Research-ready leads for this week's prospecting.

**🟢 Monitor & Nurture (Score 40-54, strong Fit but low Intent/Timing):** Add to account watch list. Set re-evaluation trigger (funding alert, job change alert, intent surge).

⭐ **Critical design principle:** Never show a rep more than 25-30 "Act Now" leads at once. Cognitive overload kills execution. Prioritization only works if the list is short enough to feel actionable. Enforce this as a hard cap with a queue mechanism — new leads enter "Act Now" as others are actioned or aged out.

### **Areas Requiring Careful AI Prompt Design (Human Judgment Flags)**

These signals are currently difficult to automate reliably and require either human review or very careful prompt engineering:

1. **Political org dynamics** — Whether a champion actually has internal credibility is nearly impossible to infer from external data. Requires human discovery.  
2. **Cultural fit signals** — Psychographic alignment between buyer philosophy and your company's approach (startup vs. enterprise sales motion mismatch, for example)  
3. **Relationship leverage** — A warm intro from a mutual connection is worth 10x a cold email, but AI can't assess relationship quality from LinkedIn connection data alone  
4. **Timing nuance in enterprise** — "Budget is available but the champion is managing a competing initiative" requires a human conversation to surface  
5. **Negative intent signals** — A company that was recently burned by a vendor in your category will show normal intent signals but carry hidden sales cycle risk

**AI Instruction Summary:** Structure every lead output as a work order containing identity, qualification, intelligence, personalization, and operational layers; enforce a hard cap of 25-30 "Act Now" leads displayed at once; present leads in three priority tiers rather than a flat ranked list; flag the five categories of human-judgment-dependent signals for rep review rather than attempting to score them programmatically.

