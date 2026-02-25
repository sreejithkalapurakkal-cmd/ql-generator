# qlGen Frontend — Technical Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Communication with Backend](#3-communication-with-backend)
4. [Key Features & Components](#4-key-features--components)
5. [Environment & Configuration](#5-environment--configuration)

---

## 1. Overview

### What the Frontend Does

The qlGen frontend is a single-page web application that provides a guided user interface for generating B2B sales leads from an Ideal Customer Profile (ICP). The user experience follows a linear workflow:

1. **Define an ICP** — Fill out a 9-step wizard capturing target offering, geographic regions, industries, company size, technology maturity, infrastructure readiness, digital transformation drivers, and leadership traits.
2. **Run the Pipeline** — Launch an AI-driven lead generation pipeline and monitor its real-time progress through four stages (Company Discovery → Contact Discovery → Enrichment → BANT Scoring).
3. **View and Export Leads** — Browse a table of qualified companies with their decision-maker contacts and BANT scores, then export to Excel (`.xlsx`) or CSV.

### Framework & Language

| Technology | Version |
|---|---|
| React | 19.2.0 |
| TypeScript | ~5.9.3 |
| Vite (build tool) | 7.3.1 |
| React Router DOM | 6.30.3 |
| Ant Design (UI library) | 6.3.1 |
| TailwindCSS | 4.2.1 |
| Axios (HTTP client) | 1.13.5 |
| Recharts (charts) | 3.7.0 |

### Folder Structure

```
frontend/
├── Dockerfile                  # Node.js production container
├── index.html                  # HTML shell with <div id="root">
├── package.json                # NPM dependencies & scripts
├── vite.config.ts              # Vite build + dev-server config (proxy, port)
├── tsconfig.json               # TypeScript root config
├── tsconfig.app.json           # TypeScript app-specific config
├── tsconfig.node.json          # TypeScript config for Vite config file itself
├── eslint.config.js            # ESLint rules (TS + React Hooks + React Refresh)
├── public/
│   └── vite.svg                # Favicon placeholder
└── src/
    ├── main.tsx                # React app bootstrap (ReactDOM.createRoot)
    ├── App.tsx                 # Root component: theme provider + all routes
    ├── index.css               # Global CSS reset and baseline styles
    ├── api/                    # API client layer (Axios wrappers)
    │   ├── client.ts           # Shared Axios instance (base URL, headers)
    │   ├── icpApi.ts           # ICP CRUD API calls
    │   ├── pipelineApi.ts      # Pipeline start / status / history API calls
    │   └── leadsApi.ts         # Leads fetch + export URL builder
    ├── types/
    │   └── index.ts            # All shared TypeScript interfaces + DEFAULT_ICP constant
    ├── components/
    │   └── layout/
    │       └── AppLayout.tsx   # Shell: dark sidebar + header + content outlet
    └── pages/
        ├── DashboardPage.tsx   # Summary statistics + recent pipeline runs
        ├── ICPConfigPage.tsx   # 9-step ICP creation / edit wizard
        ├── ICPListPage.tsx     # Table of all saved ICPs with actions
        ├── PipelinePage.tsx    # Real-time pipeline progress (SSE + polling)
        └── LeadsPage.tsx       # Leads results table + BANT details + export
```

---

## 2. Architecture

### App Bootstrapping

`src/main.tsx` mounts the React application into `<div id="root">` in `index.html`. It wraps the app in `React.StrictMode`.

`src/App.tsx` configures:
- An **Ant Design `ConfigProvider`** for global theming (primary color `#1F4E79`).
- A **`BrowserRouter`** from React Router for client-side navigation.
- All top-level **`<Route>`** definitions.

### Routing

Routing is handled by **React Router DOM v6** using `<Routes>` and `<Route>` components.

| Path | Component | Purpose |
|---|---|---|
| `/` | Redirect → `/dashboard` | Default redirect |
| `/dashboard` | `DashboardPage` | Statistics overview and pipeline history |
| `/icp/new` | `ICPConfigPage` | Create a new ICP via the 9-step wizard |
| `/icp/:id/edit` | `ICPConfigPage` | Edit an existing ICP (same wizard, pre-populated) |
| `/icp` | `ICPListPage` | Browse and manage all saved ICPs |
| `/pipeline/:runId` | `PipelinePage` | Monitor a running or completed pipeline |
| `/leads/:runId` | `LeadsPage` | View and export results from a completed pipeline |

All routes are wrapped inside the `AppLayout` component, which renders the persistent sidebar and header.

### Component Hierarchy

```
App.tsx (ConfigProvider + BrowserRouter)
└── AppLayout (sidebar + header + <Outlet>)
    ├── DashboardPage
    ├── ICPConfigPage
    ├── ICPListPage
    ├── PipelinePage
    └── LeadsPage
```

### State Management

There is **no global state management library** (no Redux, Zustand, or Context API beyond Ant Design internals). Each page component manages its own local state using React's built-in `useState` and `useEffect` hooks. Data is fetched directly from the API on component mount and stored in local state variables.

This is a deliberate design choice suited to the app's relatively linear flow — each page operates independently and data does not need to be shared across pages.

### Layout — `AppLayout.tsx`

A persistent shell component rendered around every page. It consists of:

- **Sidebar (`Sider`):** Fixed-width, dark-themed (`#001529`) sidebar with the `qlGen` brand logo/text and the main navigation `Menu` with three items:
  - **Dashboard** (`/dashboard`)
  - **ICP Configs** (`/icp`)
  - **New ICP** (`/icp/new`)
- **Header:** White horizontal bar at the top with the page title.
- **Content area:** Scrollable `<Outlet />` that renders the active page component.

---

## 3. Communication with Backend

### Protocol

The frontend communicates with the backend exclusively via **HTTP REST** using `axios`. For real-time pipeline progress, it additionally uses the browser's native **`EventSource` API** to consume a **Server-Sent Events (SSE)** stream.

### API Client — `src/api/client.ts`

A single shared Axios instance is configured with:

```typescript
const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});
```

The base URL is a **relative path** (`/api/v1`). In development, Vite's dev server proxies all `/api` requests to the backend (see [Environment & Configuration](#5-environment--configuration)). In Docker Compose, NGINX or the Vite server proxies to `http://backend:8000`.

No request or response interceptors are configured. Error handling is done inline in each page component.

### API Modules

#### `src/api/icpApi.ts` — ICP Operations

| Function | Method | Endpoint | Purpose |
|---|---|---|---|
| `createICP(data)` | `POST` | `/icp` | Save a new ICP configuration |
| `listICPs()` | `GET` | `/icp` | Fetch all active ICPs |
| `getICP(id)` | `GET` | `/icp/:id` | Fetch a single ICP by ID |
| `updateICP(id, data)` | `PUT` | `/icp/:id` | Partially update an ICP |
| `deleteICP(id)` | `DELETE` | `/icp/:id` | Soft-delete an ICP |

#### `src/api/pipelineApi.ts` — Pipeline Operations

| Function | Method | Endpoint | Purpose |
|---|---|---|---|
| `startPipeline(data)` | `POST` | `/pipeline/run` | Launch a new pipeline run |
| `getPipelineStatus(runId)` | `GET` | `/pipeline/:runId` | Poll a pipeline's current status |
| `listPipelineRuns()` | `GET` | `/pipeline/history/list` | Fetch the 50 most recent pipeline runs |

#### `src/api/leadsApi.ts` — Leads & Export

| Function | Method | Endpoint | Purpose |
|---|---|---|---|
| `getLeadCompanies(runId, params)` | `GET` | `/leads/:runId/companies` | Fetch qualified companies with optional filters |
| `getExportUrl(runId, format)` | — | `/leads/:runId/export?format=xlsx\|csv` | Build a direct download URL (no Axios call — used in `<a href>`) |

Optional query params for `getLeadCompanies`:
- `min_bant_score` — Integer filter (e.g., `12` for Warm leads and above)
- `industry_filter` — String filter by industry name
- `sort_by` — `"bant_score"` (default) or `"company_name"`

### Real-Time Pipeline Progress — SSE

`PipelinePage` opens an `EventSource` to `/api/v1/pipeline/{runId}/stream`. The event listener handles three event types:

| Event Type | Action |
|---|---|
| `stage_update` | Parse JSON payload; update current stage label and progress message in UI |
| `completed` | Show success message with company/contact counts; display "View Leads" button |
| `error` | Show error alert; close the `EventSource` |

If the `EventSource` encounters a connection error or the browser does not support SSE, the page falls back to **polling** `getPipelineStatus()` every 5 seconds.

### Authentication

**There is no authentication layer in the current codebase.** The application is designed for internal/trusted use and does not implement JWT, sessions, cookies, or OAuth. All API endpoints are publicly accessible within the network. This should be noted as a gap if the application is to be exposed publicly.

---

## 4. Key Features & Components

### DashboardPage

The landing page after login. It fetches and displays:

- **4 statistics cards** (Ant Design `Statistic`):
  - Total ICP Configurations saved
  - Total Pipeline Runs executed
  - Total Companies Found (sum across all runs)
  - Total Contacts Found (sum across all runs)

- **Recent Pipeline Runs table** with columns: Status (colored `Tag`), Companies Found, Contacts Found, Started date/time, Actions.

  | Status | Tag Color |
  |---|---|
  | `pending` | default (grey) |
  | `running` | blue / processing |
  | `completed` | green / success |
  | `failed` | red / error |

  Action buttons per run:
  - `running` → "View Progress" → navigates to `/pipeline/:runId`
  - `completed` → "View Leads" → navigates to `/leads/:runId`

- **Empty state:** Ant Design `Empty` component with a prompt to create the first ICP if no pipeline runs exist.

### ICPConfigPage — 9-Step Wizard

The most complex page. Implements a step-by-step form using Ant Design's `Steps` component combined with custom step-specific form sections. Two modes are supported:

- **Create mode** (`/icp/new`): Form initializes with `DEFAULT_ICP` values from `types/index.ts`.
- **Edit mode** (`/icp/:id/edit`): On mount, fetches the existing ICP via `getICP(id)` and pre-populates all fields.

**Wizard Steps:**

| Step | Fields |
|---|---|
| 1 — Offering | ICP Name (text), Description (textarea), Target Offerings (tag input) |
| 2 — Regions | Target Countries (tag input), Priority Areas (tag input) |
| 3 — Industry | Vertical + Sub-Vertical (add form → displayed as removable tags) |
| 4 — Company Size | Employee Min/Max (number inputs), Revenue Min/Max (number inputs), Currency selector |
| 5 — Technology Maturity | Positive tech signals (tag input), Negative tech signals (tag input) |
| 6 — Infrastructure Readiness | Infrastructure indicators (tag input) |
| 7 — Digital Transformation Drivers | Growth Triggers, Operational Pains, Competitive Pressures, Strategic Initiatives (4 separate tag inputs) |
| 8 — Leadership Traits | Target Roles, Behavioral Traits (tag inputs) |
| 9 — Review | Read-only summary of all entered data; "Save & Run Pipeline" button |

On the final step, clicking "Save & Run Pipeline":
1. Calls `createICP()` or `updateICP()` to persist the config.
2. Immediately calls `startPipeline()` with the returned ICP ID.
3. Navigates to `/pipeline/:runId` to watch progress.

### ICPListPage

A data table listing all active ICP configurations. Columns:
- **Name**
- **Description** (truncated with ellipsis)
- **Industries** (top 3 displayed as Ant Design `Tag` badges)
- **Created** (formatted date)
- **Actions:** "Run Pipeline" / "Edit" / "Delete" buttons

"Run Pipeline" starts a new pipeline for that ICP without re-entering the wizard.

"Delete" calls `deleteICP()`, which performs a soft-delete on the backend (`is_active = false`).

### PipelinePage

Monitors a single pipeline run identified by `:runId` from the URL.

**Progress UI:**
- Ant Design `Steps` component showing the 4 pipeline stages.
- A log panel displaying timestamped agent progress messages streamed via SSE.
- A spinner/loading indicator while the pipeline is running.

**Completion UI:**
- A `Result` component showing success with companies and contacts found.
- A "View Leads" button navigating to `/leads/:runId`.

**Error UI:**
- An `Alert` component with the error message from `PipelineRun.error_log`.

### LeadsPage

Displays the results of a completed pipeline run.

**Statistics row (4 cards):**
- Companies found
- Contacts found
- Average BANT Score
- Hot leads count (BANT ≥ 16)

**Leads table:**
One row per contact (company data is repeated per row). Columns:

| Column | Notes |
|---|---|
| # | Serial number |
| Company Name | Plain text |
| Website | Clickable link |
| Geo / City | City + Country |
| Contact Name | Full name |
| Designation | Job title |
| LinkedIn | Clickable icon link |
| Email | `mailto:` link |
| Phone | Plain text |
| BANT Score | Colored `Tag` badge |

**BANT Score Color Coding:**

| Score Range | Label | Color |
|---|---|---|
| ≥ 16 | Hot | Green |
| 12–15 | Warm | Gold |
| 9–11 | Cool | Blue |
| < 9 | Cold | Red |

**Expandable rows:** Each row can be expanded to show the full BANT breakdown — individual scores (1–5) and reasoning text for Budget, Authority, Need, and Timing, plus the overall summary.

**Export buttons:**
- "Export XLSX" — opens `getExportUrl(runId, 'xlsx')` directly via `window.open()` or `<a>` tag triggering a browser download.
- "Export CSV" — same mechanism with `format=csv`.

### UI Libraries & Design System

| Library | Role |
|---|---|
| **Ant Design 6** | Primary component library (Tables, Forms, Steps, Tags, Modals, Buttons, Cards, etc.) |
| **TailwindCSS 4** | Utility classes for spacing, flexbox layout, and minor style overrides |
| **Recharts** | Included as a dependency; not visibly used in current pages (reserved for future dashboard charts) |
| **@ant-design/icons** | Icon set used throughout (e.g., LinkedIn icon, action icons) |

The design language is enterprise-focused: a dark navy sidebar (`#001529`), white content area, and Ant Design's default clean component aesthetics, overridden with a custom primary color of `#1F4E79` (dark blue).

---

## 5. Environment & Configuration

### Environment Variables

The frontend reads the following variables at **Vite build time** (prefixed `VITE_`):

| Variable | Purpose | Default |
|---|---|---|
| `VITE_BACKEND_PROXY_URL` | Target for Vite's `/api` proxy (used in `vite.config.ts`) | `http://localhost:8000` |

> **Note:** `VITE_API_BASE_URL` is referenced in the `.env` file but the actual `src/api/client.ts` hardcodes the base URL as `/api/v1` (a relative path). The Vite proxy handles routing. So this variable has no effect at runtime — only `VITE_BACKEND_PROXY_URL` is actually used.

### Vite Configuration (`vite.config.ts`)

```typescript
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    host: '0.0.0.0',           // Needed for Docker container access
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_PROXY_URL || 'http://localhost:8000',
        changeOrigin: true,     // Rewrites the Origin header to the target
      },
    },
  },
})
```

In development, all requests to `/api/*` are proxied to the FastAPI backend, avoiding CORS issues entirely.

### Build & Serve

**Development:**
```bash
cd frontend
npm install
npm run dev        # Starts Vite dev server on port 3000 with HMR
```

**Production build:**
```bash
npm run build      # Outputs static files to ./dist
npm run preview    # Serves the built dist locally for verification
```

**Docker:**
The `frontend/Dockerfile` builds a production image. In Docker Compose, the frontend container runs the Vite dev server (with `host: '0.0.0.0'`) on port 3000, exposed to the host. The `VITE_BACKEND_PROXY_URL` is set to `http://backend:8000` so the proxy resolves to the backend container by Docker's internal DNS.

> **Note:** The current Docker setup runs Vite's dev server in the container, not a production NGINX serve. For production deployments, the Dockerfile should be updated to run `npm run build` and serve via NGINX or a similar static file server.

### TypeScript Configuration

- **Target:** `ES2022`
- **Module:** `ESNext`
- **JSX Transform:** `react-jsx` (no need to import React in every file)
- **Strict mode:** Enabled (`strict: true`)
- **Source maps:** Enabled for debugging

### Linting

ESLint is configured via `eslint.config.js` using the flat config format. Active plugins:
- `@typescript-eslint` — TypeScript-aware linting
- `eslint-plugin-react-hooks` — Enforces hooks rules (`rules-of-hooks`, `exhaustive-deps`)
- `eslint-plugin-react-refresh` — Warns about non-component exports that break HMR

```bash
npm run lint    # Run ESLint across all src/ files
```
